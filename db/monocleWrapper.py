import logging
import shutil
import sys
import time
from datetime import datetime, timedelta

import requests

from db.dbWrapperBase import DbWrapperBase
from utils.collections import Location
from utils.s2Helper import S2Helper

log = logging.getLogger(__name__)


class MonocleWrapper(DbWrapperBase):
    def ensure_last_updated_column(self):
        log.info(
            "Checking if last_updated column exists in raids table and creating it if necessary")

        result = self.__check_last_updated_column_exists()
        if result == 1:
            log.info("raids.last_updated already present")
            return True

        alter_query = (
            "ALTER TABLE raids "
            "ADD COLUMN last_updated int(11) NULL AFTER time_end"
        )

        self.execute(alter_query, commit=True)

        if self.__check_last_updated_column_exists() == 1:
            log.info("Successfully added last_updated column")
            return True
        else:
            log.warning(
                "Could not add last_updated column, fallback to time_spawn")
            return False

    def auto_hatch_eggs(self):
        log.info("{MonocleWrapper::auto_hatch_eggs} called")

        mon_id = self.application_args.auto_hatch_number

        if mon_id == 0:
            log.warning('You have enabled auto hatch but not the mon_id '
                        'so it will mark them as zero so they will remain unhatched...')

        now = time.time()
        query_for_count = (
            "SELECT id, fort_id, time_battle, time_end "
            "FROM raids "
            "WHERE time_battle <= %s AND time_end >= %s "
            "AND level = 5 AND IFNULL(pokemon_id, 0) = 0"
        )
        vals = (
            now, now
        )

        res = self.execute(query_for_count, vals)
        rows_that_need_hatch_count = len(res)
        log.debug("Rows that need updating: {0}".format(
            rows_that_need_hatch_count))

        if rows_that_need_hatch_count > 0:
            counter = 0
            query = (
                "UPDATE raids "
                "SET pokemon_id = %s "
                "WHERE id = %s"
            )

            for row in res:
                log.debug(row)
                vals = (
                    mon_id, row[0]
                )
                affected_rows = self.execute(query, vals, commit=True)

                if affected_rows == 1:
                    counter = counter + 1
                    if self.application_args.webhook:
                        log.debug(
                            'Sending auto hatched raid for raid id {0}'.format(row[0]))
                        self.webhook_helper.send_raid_webhook(
                            row[1], 'MON', row[2], row[3], 5, mon_id
                        )
                    else:
                        log.debug('Sending Webhook is disabled')
                elif affected_rows > 1:
                    log.error('Something is wrong with the indexing on your table you raids on this id {0}'
                              .format(row[0]))
                else:
                    log.error('The row we wanted to update did not get updated that had id {0}'
                              .format(row[0]))

            if counter == rows_that_need_hatch_count:
                log.info("{0} gym(s) were updated as part of the regular level 5 egg hatching checks"
                         .format(counter))
            else:
                log.warning(
                    'There was an issue and the number expected the hatch did not match the successful updates. '
                    'Expected {0} Actual {1}'.format(rows_that_need_hatch_count, counter))
        else:
            log.info('No Eggs due for hatching')

    def db_timestring_to_unix_timestamp(self, timestring):
        dt = datetime.strptime(timestring, '%Y-%m-%d %H:%M:%S.%f')
        unixtime = (dt - datetime(1970, 1, 1)).total_seconds()
        return unixtime

    def get_next_raid_hatches(self, delay_after_hatch, geofence_helper=None):
        db_time_to_check = time.time()

        query = (
            "SELECT time_battle, lat, lon "
            "FROM raids LEFT JOIN forts ON raids.fort_id = forts.id "
            "WHERE raids.time_end > %s AND raids.pokemon_id IS NULL"
        )

        vals = (
            db_time_to_check,
        )

        res = self.execute(query, vals)
        data = []
        for (time_battle, lat, lon) in res:
            if lat is None or lon is None:
                log.warning("lat or lng is none")
                continue
            elif geofence_helper and not geofence_helper.is_coord_inside_include_geofence([lat, lon]):
                log.debug("Excluded hatch at %s, %s since the coordinate is not inside the given include fences"
                          % (str(lat), str(lon)))
                continue
            # timestamp = self.dbTimeStringToUnixTimestamp(str(start))
            data.append((time_battle + delay_after_hatch, Location(lat, lon)))

        log.debug("Latest Q: %s" % str(data))
        return data

    def submit_raid(self, gym, pkm, lvl, start, end, type, raid_no, capture_time, unique_hash="123",
                    MonWithNoEgg=False):
        log.debug("[Crop: %s (%s) ] submit_raid: Submitting raid" %
                  (str(raid_no), str(unique_hash)))

        wh_send = False
        wh_start = 0
        wh_end = 0
        egg_hatched = False

        log.debug("[Crop: %s (%s) ] submit_raid: Submitting something of type %s"
                  % (str(raid_no), str(unique_hash), str(type)))

        log.info("Submitting gym: %s, lv: %s, start and spawn: %s, end: %s, mon: %s"
                 % (gym, lvl, start, end, pkm))

        # always insert timestamp to last_scanned to have rows change if raid has been reported before

        if MonWithNoEgg:
            start = end - (int(self.application_args.raid_time) * 60)
            query = (
                "UPDATE raids "
                "SET level = %s, time_spawn = %s, time_battle = %s, time_end = FROM_UNIXTIME(%s), "
                "pokemon_id = %s, last_updated = %s, "
                "WHERE fort_id = %s AND time_end >= %s"
            )
            vals = (
                lvl, int(float(capture_time)), start, end, pkm, int(
                    time.time()), gym, int(time.time())
            )
            # send out a webhook - this case should only occur once...
            # wh_send = True
            # wh_start = start
            # wh_end = end
        elif end is None or start is None:
            # no end or start time given, just update anything there is
            log.info(
                "Updating without end- or starttime - we should've seen the egg before")
            query = (
                "UPDATE raids "
                "SET level = %s, pokemon_id = %s, last_updated = %s, "
                "WHERE gym_id = %s AND time_end >= %s"
            )
            vals = (
                lvl, pkm, int(time.time()), gym, int(time.time())
            )

            found_end_time, end_time = self.get_raid_endtime(
                gym, raid_no, unique_hash=unique_hash)
            if found_end_time:
                wh_send = True
                wh_start = int(end_time) - 2700
                wh_end = end_time
                egg_hatched = True
            else:
                wh_send = False
        else:
            log.info("Updating everything")
            query = (
                "UPDATE raids "
                "SET level = %s, time_spawn = %s, time_battle = %s, time_end = %s, "
                "pokemon_id = %s, last_updated = %s, "
                "WHERE gym_id = %s AND time_end >= %s"
            )
            vals = (
                lvl, int(float(capture_time)), start, end, pkm, int(
                    time.time()), gym, int(time.time())
            )
            # wh_send = True
            # wh_start = start
            # wh_end = end

        affected_rows = self.execute(query, vals, commit=True)

        if affected_rows == 0 and not egg_hatched:
            # we need to insert the raid...
            if MonWithNoEgg:
                # submit mon without egg info -> we have an endtime
                log.info("Inserting mon without egg")
                start = end - 45 * 60
                query = (
                    "INSERT INTO raids (fort_id, level, time_spawn, time_battle, time_end, "
                    "pokemon_id "
                    "VALUES(%s, %s, %s, %s, %s, %s)"
                )
                vals = (
                    gym, lvl, int(float(capture_time)
                                  ), start, end, pkm, int(time.time())
                )
            elif end is None or start is None:
                log.info("Inserting without end or start")
                # no end or start time given, just inserting won't help much...
                log.warning("Useless to insert without endtime...")
                return False
            else:
                # we have start and end, mon is either with egg or we're submitting an egg
                log.info("Inserting everything")
                query = (
                    "INSERT INTO raids (fort_id, level, time_spawn, time_battle, time_end, "
                    "pokemon_id "
                    "VALUES (%s, %s, %s, %s, %s, %s)"
                )
                vals = (gym, lvl, int(float(capture_time)),
                        start, end, pkm, int(time.time()))

            self.execute(query, vals, commit=True)

            wh_send = True
            if MonWithNoEgg:
                wh_start = int(end) - 2700
            else:
                wh_start = start
            wh_end = end
            if pkm is None:
                pkm = 0

        log.info("[Crop: %s (%s) ] submit_raid: Submit finished"
                 % (str(raid_no), str(unique_hash)))
        self.refresh_times(gym, raid_no, capture_time)

        if self.application_args.webhook and wh_send:
            log.info('[Crop: ' + str(raid_no) + ' (' +
                     str(unique_hash) + ') ] ' + 'submitRaid: Send webhook')
            self.webhook_helper.send_raid_webhook(
                gym, 'RAID', wh_start, wh_end, lvl, pkm
            )

        return True

    def read_raid_endtime(self, gym, raid_no, unique_hash="123"):
        log.debug("[Crop: %s (%s) ] read_raid_endtime: Check DB for existing mon"
                  % (str(raid_no), str(unique_hash)))
        now = time.time()

        query = (
            "SELECT time_end "
            "FROM raids "
            "WHERE time_end >= %s AND fort_id = %s"
        )
        vals = (
            now, gym
        )

        res = self.execute(query, vals)
        number_of_rows = len(res)

        if number_of_rows > 0:
            log.debug("[Crop: %s (%s) ] read_raid_endtime: Found Rows: %s"
                      % (str(raid_no), str(unique_hash), str(number_of_rows)))
            log.info("[Crop: %s (%s) ] read_raid_endtime: Endtime already submitted"
                     % (str(raid_no), str(unique_hash)))
            return True
        else:
            log.info("[Crop: %s (%s) ] read_raid_endtime: Endtime is new"
                     % (str(raid_no), str(unique_hash)))
            return False

    def get_raid_endtime(self, gym, raid_no, unique_hash="123"):
        log.debug("[Crop: %s (%s) ] get_raid_endtime: Check DB for existing mon"
                  % (str(raid_no), str(unique_hash)))

        now = time.time()
        query = (
            "SELECT time_end "
            "FROM raids "
            "WHERE time_end >= %s AND fort_id = %s"
        )
        vals = (
            now, gym
        )

        res = self.execute(query, vals)
        number_of_rows = len(res)

        if number_of_rows > 0:
            for row in res:
                log.debug("[Crop: %s (%s) ] get_raid_endtime: Returning found endtime"
                          % (str(raid_no), str(unique_hash)))
                log.debug("[Crop: %s (%s) ] get_raid_endtime: Time: %s"
                          % (str(raid_no), str(unique_hash), str(row[0])))

                return True, row[0]

        log.debug("[Crop: %s (%s) ] get_raid_endtime: No matching endtime found"
                  % (str(raid_no), str(unique_hash)))
        return False, None

    def raid_exist(self, gym, type, raid_no, unique_hash="123", mon=0):
        log.debug("[Crop: %s (%s) ] raid_exist: Check DB for existing entry"
                  % (str(raid_no), str(unique_hash)))
        now = time.time()

        # TODO: consider reducing the code...

        if type == "EGG":
            log.debug("[Crop: %s (%s) ] raid_exist: Check for EGG"
                      % (str(raid_no), str(unique_hash)))
            query = (
                "SELECT time_spawn "
                "FROM raids "
                "WHERE time_spawn >= %s AND fort_id = %s"
            )
            vals = (
                now, gym
            )

            res = self.execute(query, vals)
            number_of_rows = len(res)
            if number_of_rows > 0:
                log.debug("[Crop: %s (%s) ] raid_exist: Found Rows: %s"
                          % (str(raid_no), str(unique_hash), str(number_of_rows)))
                log.info("[Crop: %s (%s) ] raid_exist: Egg already submitted"
                         % (str(raid_no), str(unique_hash)))
                return True
            else:
                log.info("[Crop: %s (%s) ] raid_exist: Egg is new"
                         % (str(raid_no), str(unique_hash)))
                return False
        else:
            log.debug("[Crop: %s (%s) ] raid_exist: Check for EGG"
                      % (str(raid_no), str(unique_hash)))
            query = (
                "SELECT count(*) "
                "FROM raids "
                "WHERE time_spawn <= %s "
                "AND time_end >= %s "
                "AND fort_id = %s "
                "AND pokemon_id IS NOT NULL"
            )
            vals = (
                now, now, gym, mon
            )

            res = self.execute(query, vals)
            number_of_rows = len(res)
            if number_of_rows > 0:
                log.debug("[Crop: %s (%s) ] raid_exist: Found Rows: %s"
                          % (str(raid_no), str(unique_hash), str(number_of_rows)))
                log.info("[Crop: %s (%s) ] raid_exist: Mon already submitted"
                         % (str(raid_no), str(unique_hash)))
                return True
            else:
                log.info("[Crop: %s (%s) ] raid_exist: Mon is new"
                         % (str(raid_no), str(unique_hash)))
                return False

    def refresh_times(self, gym, raid_no, capture_time, unique_hash="123"):
        log.debug("[Crop: %s (%s) ] raid_exist: Check for EGG"
                  % (str(raid_no), str(unique_hash)))
        now = int(time.time())

        query = (
            "UPDATE fort_sightings "
            "SET last_modified = %s, updated = %s "
            "WHERE fort_id = %s"
        )
        vals = (
            now, now, gym
        )
        self.execute(query, vals, commit=True)

    def get_near_gyms(self, lat, lng, hash, raid_no, dist, unique_hash="123"):
        if dist == 99:
            distance = str(9999)
            lat = self.application_args.home_lat
            lng = self.application_args.home_lng
        else:
            distance = str(self.application_args.gym_scan_distance)

        query = (
            "SELECT id, "
            "( 6371 * "
            "acos( "
            "cos(radians(%s)) "
            "* cos(radians(lat)) "
            "* cos(radians(lon) - radians(%s)) "
            "+ sin(radians(%s)) "
            "* sin(radians(lat))"
            ")"
            ") "
            "FROM forts "
            "HAVING distance <= %s OR distance IS NULL "
            "ORDER BY distance"
        )
        vals = (
            float(lat), float(lng), float(lat), float(dist)
        )
        data = []
        res = self.execute(query, vals)
        for (id, distance) in res:
            data.append(id)
        return data

    def set_scanned_location(self, lat, lng, capture_time):
        log.debug(
            "MonocleWrapper::set_scanned_location: Scanned location not supported with monocle")
        pass

    def download_gym_images(self):
        import json
        import io
        import os
        gyminfo = {}

        url_image_path = os.getcwd() + '/ocr/gym_img/'

        file_path = os.path.dirname(url_image_path)
        if not os.path.exists(file_path):
            os.makedirs(file_path)

        query = (
            "SELECT forts.id, forts.lat, forts.lon, forts.name, forts.url, "
            "IFNULL(forts.park, 'unknown'), forts.sponsor, fort_sightings.team "
            "FROM forts "
            "LEFT JOIN fort_sightings ON forts.id = fort_sightings.id"
        )

        res = self.execute(query)

        for (id, lat, lon, name, url, park, sponsor, team) in res:
            if url is not None:
                if not self.application_args.justjson:
                    filename = url_image_path + '_' + str(id) + '_.jpg'
                    log.debug('Downloading', filename)
                    self.__download_img(str(url), str(filename))
                gyminfo[id] = self.__encode_hash_json(team, float(lat), float(lon), str(
                    name).replace('"', '\\"').replace('\n', '\\n'), url, park, sponsor)

        with io.open('gym_info.json', 'w') as outfile:
            outfile.write(str(json.dumps(gyminfo, indent=4, sort_keys=True)))
        log.info('Finished downloading gym images...')

        return True

    def get_gym_infos(self, id=False):
        gyminfo = {}

        query = (
            "SELECT forts.external_id, forts.lat, forts.lon, forts.name, forts.url, "
            "IFNULL(forts.park, 'unknown'), IFNULL(forts.sponsor,0), fort_sightings.team "
            "FROM forts "
            "INNER JOIN fort_sightings ON forts.id = fort_sightings.fort_id "
            "WHERE forts.external_id IS NOT NULL "
        )

        res = self.execute(query)

        for (external_id, lat, lon, name, url, park, sponsor, team) in res:
            gyminfo[external_id] = self.__encode_hash_json(team, float(lat), float(lon), str(
                name).replace('"', '\\"').replace('\n', '\\n'), str(url), park, sponsor)
        return gyminfo

    def gyms_from_db(self, geofence_helper):
        log.info('Downloading gym coords from DB')

        query = (
            "SELECT lat, lon "
            "FROM forts"
        )

        res = self.execute(query)
        list_of_coords = []
        for (lat, lon) in res:
            list_of_coords.append([lat, lon])

        if geofence_helper is not None:
            geofenced_coords = geofence_helper.get_geofenced_coordinates(
                list_of_coords)
            return geofenced_coords
        else:
            import numpy as np
            to_return = np.zeros(shape=(len(list_of_coords), 2))
            for i in range(len(to_return)):
                to_return[i][0] = list_of_coords[i][0]
                to_return[i][1] = list_of_coords[i][1]
            return to_return

    def stops_from_db(self, geofence_helper):
        log.info('Downloading pokestop coords from DB')

        query = (
            "SELECT lat, lon     "
            "FROM pokestops"
        )

        res = self.execute(query)
        list_of_coords = []
        for (lat, lon) in res:
            list_of_coords.append([lat, lon])

        if geofence_helper is not None:
            geofenced_coords = geofence_helper.get_geofenced_coordinates(
                list_of_coords)
            return geofenced_coords
        else:
            import numpy as np
            to_return = np.zeros(shape=(len(list_of_coords), 2))
            for i in range(len(to_return)):
                to_return[i][0] = list_of_coords[i][0]
                to_return[i][1] = list_of_coords[i][1]
            return to_return

    def update_insert_weather(self, cell_id, gameplay_weather, capture_time, cloud_level=0, rain_level=0, wind_level=0,
                              snow_level=0, fog_level=0, wind_direction=0, weather_daytime=0):
        now = time.time()
        query = (
            "INSERT INTO weather "
            "(s2_cell_id, `condition`, alert_severity, warn, day, updated) "
            "VALUES (%s, %s, %s, %s, %s, %s) "
            "ON DUPLICATE KEY UPDATE `condition` = VALUES(`condition`), "
            "alert_severity = VALUES(alert_severity), warn=VALUES(warn), "
            "day=VALUES(day), updated=VALUES(updated)"
        )
        vals = (
            cell_id, gameplay_weather, 0, 0, weather_daytime, int(float(now))
        )

        self.execute(query, vals, commit=True)

        self.webhook_helper.send_weather_webhook(
            cell_id, gameplay_weather, 0, 0, 2, float(now)
        )

    def submit_mon_iv(self, origin, timestamp, encounter_proto):
        log.debug("Updating IV sent by %s" % str(origin))
        wild_pokemon = encounter_proto.get("wild_pokemon", None)
        if wild_pokemon is None:
            return
        now = time.time()
        despawn_time = datetime.now() + timedelta(seconds=300)
        despawn_time_unix = int(time.mktime(despawn_time.timetuple()))
        despawn_time = datetime.utcfromtimestamp(
            time.mktime(despawn_time.timetuple())
        ).strftime('%Y-%m-%d %H:%M:%S')
        init = True
        getdetspawntime = self.get_detected_endtime(
            int(str(wild_pokemon["spawnpoint_id"]), 16))

        if getdetspawntime:
            despawn_time_unix = self._gen_endtime(getdetspawntime)
            despawn_time = datetime.utcfromtimestamp(
                despawn_time_unix
            ).strftime('%Y-%m-%d %H:%M:%S')
            init = False

        latitude = wild_pokemon.get("latitude")
        longitude = wild_pokemon.get("longitude")
        pokemon_data = wild_pokemon.get("pokemon_data")

        if init:
            log.info("{0}: updating mon #{1} at {2}, {3}. Despawning at {4} (init)".format(
                str(origin),
                pokemon_data["id"],
                latitude, longitude,
                despawn_time))
        else:
            log.info("{0}: updating mon #{1} at {2}, {3}. Despawning at {4} (non-init)".format(
                str(origin),
                pokemon_data["id"],
                latitude, longitude,
                despawn_time))

        # calculating level
        if pokemon_data.get("cp_multiplier") < 0.734:
            pokemon_level = (58.35178527 * pokemon_data.get("cp_multiplier") * pokemon_data.get(
                "cp_multiplier") - 2.838007664 * pokemon_data.get("cp_multiplier") + 0.8539209906)
        else:
            pokemon_level = 171.0112688 * \
                pokemon_data.get("cp_multiplier") - 95.20425243

            pokemon_level = round(pokemon_level) * 2 / 2

        pokemon_display = pokemon_data.get("display")
        if pokemon_display is None:
            pokemon_display = {}
            # initialize to not run into nullpointer

        s2_weather_cell_id = S2Helper.lat_lng_to_cell_id(
            latitude, longitude, level=10)

        encounter_id = wild_pokemon['encounter_id']

        if encounter_id < 0:
            encounter_id = encounter_id + 2**64

        query = (
            "INSERT INTO sightings (pokemon_id, spawn_id, expire_timestamp, encounter_id, "
            "lat, lon, updated, gender, form, weather_boosted_condition, weather_cell_id, "
            "atk_iv, def_iv, sta_iv, move_1, move_2, cp, level, weight) "
            "VALUES(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) "
            "ON DUPLICATE KEY UPDATE updated=VALUES(UPDATED), atk_iv=VALUES(atk_iv), def_iv=VALUES(def_iv), "
            "sta_iv=VALUES(sta_iv), move_1=VALUES(move_1), move_2=VALUES(move_2), cp=VALUES(cp), "
            "level=VALUES(level), weight=VALUES(weight)"
        )
        vals = (
            pokemon_data["id"],
            int(wild_pokemon.get("spawnpoint_id"), 16),
            despawn_time_unix,
            encounter_id,
            latitude, longitude, timestamp,
            pokemon_display.get("gender_value", None),
            pokemon_display.get("form_value", None),
            pokemon_display.get("weather_boosted_value", None),
            s2_weather_cell_id,
            pokemon_data.get("individual_attack"),
            pokemon_data.get("individual_defense"),
            pokemon_data.get("individual_stamina"),
            pokemon_data.get("move_1"),
            pokemon_data.get("move_2"),
            pokemon_data.get("cp"),
            pokemon_level,
            pokemon_data.get("weight"),
        )

        self.execute(query, vals, commit=True)

        self.webhook_helper.send_pokemon_webhook(
            encounter_id=encounter_id,
            pokemon_id=pokemon_data.get("id"),
            last_modified_time=timestamp,
            spawnpoint_id=int(wild_pokemon.get("spawnpoint_id"), 16),
            lat=latitude, lon=longitude,
            despawn_time_unix=despawn_time_unix,
            pokemon_level=pokemon_level,
            cp_multiplier=pokemon_data.get("cp_multiplier"),
            form=pokemon_display.get("form_value", None),
            cp=pokemon_data.get("cp"),
            individual_attack=pokemon_data.get("individual_attack"),
            individual_defense=pokemon_data.get("individual_defense"),
            individual_stamina=pokemon_data.get("individual_stamina"),
            move_1=pokemon_data.get("move_1"),
            move_2=pokemon_data.get("move_2"),
            height=pokemon_data.get("height"),
            weight=pokemon_data.get("weight")
        )

    def submit_mons_map_proto(self, origin, map_proto, mon_ids_iv):
        cells = map_proto.get("cells", None)
        if cells is None:
            return False
        query_mons = (
            "INSERT INTO sightings (pokemon_id, spawn_id, expire_timestamp, encounter_id, "
            "lat, lon, updated, gender, form, weather_boosted_condition, weather_cell_id) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) "
            "ON DUPLICATE KEY UPDATE updated=VALUES(updated)"
        )

        mon_vals = []
        for cell in cells:
            for wild_mon in cell['wild_pokemon']:
                spawnid = int(str(wild_mon['spawnpoint_id']), 16)
                lat = wild_mon['latitude']
                lon = wild_mon['longitude']
                s2_weather_cell_id = S2Helper.lat_lng_to_cell_id(
                    lat, lon, level=10)

                despawn_time = datetime.now() + timedelta(seconds=300)
                despawn_time_unix = int(time.mktime(despawn_time.timetuple()))
                now = int(time.time())
                init = True

                getdetspawntime = self.get_detected_endtime(str(spawnid))

                if getdetspawntime:
                    despawn_time = self._gen_endtime(getdetspawntime)
                    despawn_time_unix = despawn_time
                    init = False

                if init:
                    log.info("{0}: adding mon with id #{1} at {2}, {3}. Despawning at {4} (init)"
                             .format(str(origin), wild_mon['pokemon_data']['id'], lat, lon, despawn_time))
                else:
                    log.info("{0}: adding mon with id #{1} at {2}, {3}. Despawning at {4} (non-init)"
                             .format(str(origin), wild_mon['pokemon_data']['id'], lat, lon, despawn_time))

                mon_id = wild_mon['pokemon_data']['id']
                encounter_id = wild_mon['encounter_id']

                if encounter_id < 0:
                    encounter_id = encounter_id + 2**64

                if mon_ids_iv is not None and mon_id not in mon_ids_iv or mon_ids_iv is None:
                    self.webhook_helper.send_pokemon_webhook(
                        encounter_id, mon_id, time.time(),
                        spawnid, lat, lon, despawn_time_unix
                    )

                mon_vals.append(
                    (
                        mon_id,
                        spawnid,
                        despawn_time_unix,
                        encounter_id,
                        lat, lon,
                        now,
                        wild_mon['pokemon_data']['display']['gender_value'],
                        wild_mon['pokemon_data']['display']['form_value'],
                        wild_mon['pokemon_data']['display']['weather_boosted_value'],
                        s2_weather_cell_id
                    )
                )

        self.executemany(query_mons, mon_vals, commit=True)
        return True

    def submit_pokestops_map_proto(self, origin, map_proto):
        log.debug("Inserting/Updating pokestops sent by %s" % str(origin))
        cells = map_proto.get("cells", None)
        if cells is None:
            return False
        pokestop_vals = []
        # now = datetime.datetime.utcfromtimestamp(time.time()).strftime("%Y-%m-%d %H:%M:%S")

        query_pokestops = (
            "INSERT INTO pokestops (external_id, lat, lon, name, url, updated, expires) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s) "
            "ON DUPLICATE KEY UPDATE updated=VALUES(updated), expires=VALUES(expires)"
        )

        for cell in cells:
            for fort in cell['forts']:
                if fort['type'] == 1:
                    pokestop_vals.append(
                        self.__extract_args_single_pokestop(fort))
        self.executemany(query_pokestops, pokestop_vals, commit=True)
        return True

    def submit_gyms_map_proto(self, origin, map_proto):
        log.debug("Inserting/Updating gyms sent by %s" % str(origin))
        cells = map_proto.get("cells", None)
        if cells is None:
            return False

        now = int(time.time())

        vals_forts = []
        vals_fort_sightings_insert = []
        vals_fort_sightings_update = []

        query_forts = (
            "INSERT IGNORE INTO forts (external_id, lat, lon, name, url, "
            "sponsor, weather_cell_id, parkid, park) "
            "VALUES(%s, %s, %s, %s, %s, %s, %s, %s, %s)"
        )

        query_fort_sightings_insert = (
            "INSERT INTO fort_sightings (fort_id, last_modified, team, guard_pokemon_id, "
            "slots_available, is_in_battle, updated) "
            "VALUES ((SELECT id FROM forts WHERE external_id = %s), %s, %s, %s, %s, %s, %s)"
        )

        query_fort_sightings_update = (
            "UPDATE fort_sightings SET team = %s, guard_pokemon_id = %s, "
            "slots_available = %s, updated = %s, last_modified = %s, "
            "is_in_battle=%s "
            "WHERE fort_id=(SELECT id FROM forts WHERE external_id=%s)"
        )

        for cell in cells:
            for gym in cell['forts']:
                if gym['type'] == 0:
                    gym_id = gym['id']
                    guardmon = gym['gym_details']['guard_pokemon']
                    lat = gym['latitude']
                    lon = gym['longitude']
                    image_uri = gym['image_url']
                    s2_cell_id = S2Helper.lat_lng_to_cell_id(lat, lon)
                    team = gym['gym_details']['owned_by_team']
                    slots = gym['gym_details']['slots_available']
                    is_in_battle = gym['gym_details'].get(
                        'is_in_battle', False)
                    if is_in_battle:
                        is_in_battle = 1
                    else:
                        is_in_battle = 0

                    raidendSec = 0
                    if gym['gym_details']['has_raid']:
                        raidendSec = int(
                            gym['gym_details']['raid_info']['raid_end'] / 1000)

                    self.webhook_helper.send_gym_webhook(
                        gym_id, raidendSec, 'unknown', team, slots, guardmon, lat, lon
                    )

                    vals_forts.append(
                        (
                            gym_id, lat, lon, None, image_uri, None, s2_cell_id, None, None
                        )
                    )

                    query_get_count = "SELECT count(*) from fort_sightings where fort_id=(SELECT id from forts where " \
                                      "external_id = %s)"
                    vals_get_count = (gym_id,)
                    res = self.execute(query_get_count, vals_get_count)

                    fort_sightings_exists = res[0]
                    fort_sightings_exists = ",".join(
                        map(str, fort_sightings_exists))

                    if int(fort_sightings_exists) == 0:
                        vals_fort_sightings_insert.append(
                            (
                                gym_id, now, team, guardmon, slots, is_in_battle, now
                            )
                        )
                    else:
                        vals_fort_sightings_update.append(
                            (
                                team, guardmon, slots, now, now, is_in_battle, gym_id
                            )
                        )
        self.executemany(query_forts, vals_forts, commit=True)
        self.executemany(query_fort_sightings_insert,
                         vals_fort_sightings_insert, commit=True)
        self.executemany(query_fort_sightings_update,
                         vals_fort_sightings_update, commit=True)
        return True

    def submit_raids_map_proto(self, origin, map_proto):
        cells = map_proto.get("cells", None)
        if cells is None:
            return False
        raid_vals = []
        # now = datetime.datetime.utcfromtimestamp(time.time()).strftime("%Y-%m-%d %H:%M:%S")
        now = time.time()
        query_raid = (
            "INSERT INTO raids (external_id, fort_id, level, pokemon_id, time_spawn, time_battle, "
            "time_end, last_updated, cp, move_1, move_2, form) "
            "VALUES( (SELECT id FROM forts WHERE forts.external_id=%s), "
            "(SELECT id FROM forts WHERE forts.external_id=%s), %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) "
            "ON DUPLICATE KEY UPDATE level=VALUES(level), pokemon_id=VALUES(pokemon_id), "
            "time_spawn=VALUES(time_spawn), time_battle=VALUES(time_battle), time_end=VALUES(time_end), "
            "last_updated=VALUES(last_updated), cp=VALUES(cp), move_1=VALUES(move_1), move_2=VALUES(move_2), "
            "form=VALUES(form)"
        )

        for cell in cells:
            for gym in cell['forts']:
                if gym['type'] == 0 and gym['gym_details']['has_raid']:
                    if gym['gym_details']['raid_info']['has_pokemon']:
                        pokemon_id = gym['gym_details']['raid_info']['raid_pokemon']['id']
                        cp = gym['gym_details']['raid_info']['raid_pokemon']['cp']
                        move_1 = gym['gym_details']['raid_info']['raid_pokemon']['move_1']
                        move_2 = gym['gym_details']['raid_info']['raid_pokemon']['move_2']
                        form = gym['gym_details']['raid_info']['raid_pokemon']['display']['form_value']
                    else:
                        pokemon_id = None
                        cp = 0
                        move_1 = 1
                        move_2 = 2
                        form = None

                    raidendSec = int(gym['gym_details']
                                     ['raid_info']['raid_end'] / 1000)
                    raidspawnSec = int(
                        gym['gym_details']['raid_info']['raid_spawn'] / 1000)
                    raidbattleSec = int(
                        gym['gym_details']['raid_info']['raid_battle'] / 1000)

                    level = gym['gym_details']['raid_info']['level']
                    gymid = gym['id']
                    team = gym['gym_details']['owned_by_team']

                    # gymid, type, start, end, lvl, mon, gyminfos
                    # TODO: get matching weather...
                    self.webhook_helper.send_raid_webhook(
                        gymid=gymid, type='RAID', start=raidbattleSec, end=raidendSec, lvl=level,
                        mon=pokemon_id, team_param=team, cp_param=cp, move1_param=move_1,
                        move2_param=move_2, lat_param=gym['latitude'], lng_param=gym['longitude'],
                        image_url=gym['image_url']
                    )

                    log.info("%s: adding/Updating gym at gym %s with level %s ending at %s"
                             % (str(origin), str(gymid), str(level), str(raidendSec)))

                    raid_vals.append(
                        (
                            gymid,
                            gymid,
                            level,
                            pokemon_id,
                            raidspawnSec,
                            raidbattleSec,
                            raidendSec,
                            now,
                            cp, move_1, move_2,
                            form
                        )
                    )
        self.executemany(query_raid, raid_vals, commit=True)
        log.debug("%s: done submitting raids" % str(origin))
        return True

    def submit_weather_map_proto(self, origin, map_proto, received_timestamp):
        log.debug("Inserting/updating weather sent by %s" % str(origin))
        cells = map_proto.get("cells", None)
        if cells is None:
            return False

        query_weather_insert = (
            "INSERT INTO weather (s2_cell_id, `condition`, alert_severity, warn, day, updated) "
            "VALUES (%s, %s, %s, %s, %s, %s) "
        )
        query_weather_update = (
            "UPDATE weather set `condition`=%s, alert_severity=%s, "
            "warn=%s, day=%s, updated=%s where id = %s"
        )

        list_of_weather_vals = []
        list_of_weather_updates_vals = []
        list_of_weather_inserts_vals = []

        for client_weather in map_proto['client_weather']:
            # lat, lng, alt = S2Helper.get_position_from_cell(weather_extract['cell_id'])
            time_of_day = map_proto.get("time_of_day_value", 0)
            list_of_weather_vals.append(
                self.__extract_args_single_weather(
                    client_weather, time_of_day, received_timestamp)
            )

        for weather_data in list_of_weather_vals:
            query = (
                "SELECT id "
                "FROM weather "
                "WHERE s2_cell_id = %s"
            )
            vals = (
                weather_data[0],
            )

            res = self.execute(query, vals)

            number_of_rows = len(res)

            if number_of_rows > 0:
                dbid = ",".join(map(str, res[0]))
                list_of_weather_updates_vals.append((weather_data[1], weather_data[2], weather_data[3],
                                                     weather_data[4], weather_data[5], dbid))
            else:
                list_of_weather_inserts_vals.append((weather_data[0], weather_data[1], weather_data[2],
                                                     weather_data[3], weather_data[4], weather_data[5]))

        self.executemany(query_weather_insert,
                         list_of_weather_inserts_vals, commit=True)
        self.executemany(query_weather_update,
                         list_of_weather_updates_vals, commit=True)
        return True

    def __check_last_updated_column_exists(self):
        query = (
            "SELECT count(*) "
            "FROM information_schema.columns "
            "WHERE table_name = 'raids' "
            "AND column_name = 'last_updated' "
            "AND table_schema = %s"
        )
        vals = (
            self.database,
        )

        return int(self.execute(query, vals)[0][0])

    def get_to_be_encountered(self, geofence_helper, min_time_left_seconds, eligible_mon_ids):
        if min_time_left_seconds is None or eligible_mon_ids is None:
            log.warning("MonocleWrapper::get_to_be_encountered: Not returning any encounters since no time left or "
                        "eligible mon IDs specified")
            return []
        log.debug("Getting mons to be encountered")
        query = (
            "SELECT lat, lon, encounter_id, expire_timestamp, pokemon_id "
            "FROM sightings "
            "WHERE atk_iv IS NULL AND def_iv IS NULL AND sta_iv IS NULL AND encounter_id != 0 "
            "AND expire_timestamp - %s > %s "
            "ORDER BY sightings.expire_timestamp ASC"
        )
        vals = (
            int(min_time_left_seconds), int(time.time())
        )

        results = self.execute(query, vals, commit=False)

        next_to_encounter = []
        i = 0
        for lat, lon, encounter_id, expire_timestamp, pokemon_id in results:
            if pokemon_id not in eligible_mon_ids:
                continue
            elif lat is None or lon is None:
                log.warning("lat or lng is none")
                continue
            elif geofence_helper and not geofence_helper.is_coord_inside_include_geofence([lat, lon]):
                log.debug("Excluded encounter at %s, %s since the coordinate is not inside the given include fences"
                          % (str(lat), str(lon)))
                continue

            next_to_encounter.append(
                (
                    i, Location(lat, lon), encounter_id
                )
            )
            i += 1
        return next_to_encounter

    def __download_img(self, url, file_name):
        retry = 1
        while retry <= 5:
            try:
                r = requests.get(url, stream=True, timeout=5)
                if r.status_code == 200:
                    with open(file_name, 'wb') as f:
                        r.raw.decode_content = True
                        shutil.copyfileobj(r.raw, f)
                    break
            except KeyboardInterrupt:
                log.info('Ctrl-C interrupted')
                sys.exit(1)
            except Exception as e:
                retry = retry + 1
                log.info('Download error', url)
                if retry <= 5:
                    log.info('retry:', retry)
                else:
                    log.info('Failed to download after 5 retry')

    def __encode_hash_json(self, team_id, latitude, longitude, name, url, park, sponsor):
        gym_json = {'team_id': team_id, 'latitude': latitude, 'longitude': longitude, 'name': name, 'description': '',
                    'url': url, 'park': park}

        if sponsor is not None:
            gym_json['sponsor'] = sponsor
        else:
            gym_json['sponsor'] = 0
        log.debug(gym_json)

        return gym_json

    def __extract_args_single_pokestop(self, stop_data):
        if stop_data['type'] != 1:
            log.warning("%s is not a pokestop" % str(stop_data))
            return None

        now = int(time.time())
        # lure = int(float(stop_data['lure_expires']))
        lure = 0
        if lure > 0:
            lure = lure / 1000
        return (
            stop_data['id'], stop_data['latitude'], stop_data['longitude'], "unknown",
            stop_data['image_url'], now, lure
        )

    def __extract_args_single_weather(self, client_weather_data, time_of_day, received_timestamp):
        cell_id = client_weather_data["cell_id"]
        # realLat, realLng = S2Helper.middle_of_cell(cell_id)

        # TODO: local vars
        display_weather_data = client_weather_data.get("display_weather", None)
        if display_weather_data is None:
            return None
        elif time_of_day == 2 and client_weather_data["gameplay_weather"]["gameplay_condition"] == 3:
            gameplay_weather = 13
        else:
            gameplay_weather = client_weather_data["gameplay_weather"]["gameplay_condition"]

        self.webhook_helper.send_weather_webhook(cell_id, gameplay_weather, 0, 0,
                                                 time_of_day, float(received_timestamp))
        return (
            cell_id,
            gameplay_weather,
            0, 0,
            time_of_day,
            int(round(received_timestamp))
        )

    def check_stop_quest(self, latitude, longitude):
        log.debug("{MonocleWrapper::stops_from_db} called")
        query = (
            "SELECT trs_quest.GUID "
            "from trs_quest inner join pokestops on pokestops.external_id = trs_quest.GUID where "
            "from_unixtime(trs_quest.quest_timestamp,'%Y-%m-%d') = date_format(DATE_ADD( now() , INTERVAL '-15' MINUTE ), '%Y-%m-%d') "
            "and pokestops.lat=%s and pokestops.lon=%s"
        )
        data = (latitude, longitude)

        res = self.execute(query, data)
        number_of_rows = len(res)
        if number_of_rows > 0:
            log.debug('Pokestop has already a quest with CURDATE()')
            return True
        else:
            log.debug('Pokestop has not a quest with CURDATE()')
            return False

    def quests_from_db(self, GUID=False):
        log.debug("{MonocleWrapper::quests_from_db} called")
        questinfo = {}

        if not GUID:
            query = (
                "SELECT pokestops.external_id, pokestops.lat, pokestops.lon, trs_quest.quest_type, "
                "trs_quest.quest_stardust, trs_quest.quest_pokemon_id, trs_quest.quest_reward_type, "
                "trs_quest.quest_item_id, trs_quest.quest_item_amount, "
                "pokestops.name, pokestops.url, trs_quest.quest_target, trs_quest.quest_condition, "
                "trs_quest.quest_timestamp,trs_quest.quest_task "
                "FROM pokestops inner join trs_quest on "
                "(pokestops.external_id COLLATE utf8mb4_general_ci) = trs_quest.GUID where "
                "DATE(from_unixtime(trs_quest.quest_timestamp,'%Y-%m-%d')) = CURDATE()"
            )
            data = ()
        else:
            query = (
                "SELECT pokestops.external_id, pokestops.lat, pokestops.lon, trs_quest.quest_type, "
                "trs_quest.quest_stardust, trs_quest.quest_pokemon_id, trs_quest.quest_reward_type, "
                "trs_quest.quest_item_id, trs_quest.quest_item_amount, "
                "pokestops.name, pokestops.url, trs_quest.quest_target, trs_quest.quest_condition, "
                "trs_quest.quest_timestamp,trs_quest.quest_task "
                "FROM pokestops inner join trs_quest on "
                "(pokestops.external_id COLLATE utf8mb4_general_ci)= trs_quest.GUID where "
                "DATE(from_unixtime(trs_quest.quest_timestamp,'%Y-%m-%d')) = CURDATE() and "
                "trs_quest.GUID = %s"
            )
            data = (GUID, )

        res = self.execute(query, data)

        for (pokestop_id, latitude, longitude, quest_type, quest_stardust, quest_pokemon_id, quest_reward_type,
             quest_item_id, quest_item_amount, name, image, quest_target, quest_condition,
             quest_timestamp, quest_task) in res:
            mon = "%03d" % quest_pokemon_id
            questinfo[pokestop_id] = ({
                'pokestop_id': pokestop_id, 'latitude': latitude, 'longitude': longitude,
                'quest_type': quest_type, 'quest_stardust': quest_stardust,
                'quest_pokemon_id': mon,
                'quest_reward_type': quest_reward_type, 'quest_item_id': quest_item_id,
                'quest_item_amount': quest_item_amount, 'name': name, 'image': image,
                'quest_target': quest_target,
                'quest_condition': quest_condition, 'quest_timestamp': quest_timestamp,
                'task': quest_task})
        return questinfo

    def submit_pokestops_details_map_proto(self, map_proto):
        log.debug("{MonocleWrapper::submit_pokestops_details_map_proto} called")
        pokestop_args = []
        # now = datetime.datetime.utcfromtimestamp(time.time()).strftime("%Y-%m-%d %H:%M:%S")

        query_pokestops = (
            "UPDATE pokestops set name = %s, url= %s, updated = %s, lat = %s, lon = %s "
            "where external_id = %s"
        )

        pokestop_args = self.__extract_args_single_pokestop_details(map_proto)

        if pokestop_args is not None:
            self.execute(query_pokestops, pokestop_args, commit=True)
        return True

    def __extract_args_single_pokestop_details(self, stop_data):
        if stop_data.get('type', 999) != 1:
            return None
        image = stop_data.get('image_urls', None)
        name = stop_data.get('name', None)
        now = datetime.utcfromtimestamp(
            time.time()).strftime("%Y-%m-%d %H:%M:%S")

        return name, image[0], now, stop_data['latitude'], stop_data['longitude'], stop_data['fort_id']
