import calendar
import shutil
import sys
import time
from datetime import datetime, timedelta, timezone
from functools import reduce
from multiprocessing.managers import SyncManager
from typing import List, Optional

import requests

from db.dbWrapperBase import DbWrapperBase
from utils.collections import Location
from utils.logging import logger
from utils.s2Helper import S2Helper


class MonocleWrapperManager(SyncManager):
    pass


class MonocleWrapper(DbWrapperBase):
    def __init__(self, args):
        super().__init__(args)

        self.__ensure_columns_exist()

    def __ensure_columns_exist(self):
        fields = [
            {
                "table": "raids",
                "column": "last_updated",
                "ctype": "int(11) NULL"
            },
            {
                "table": "raids",
                "column": "is_exclusive",
                "ctype": "tinyint(1) NULL"
            },
            {
                "table": "raids",
                "column": "gender",
                "ctype": "tinyint(1) NULL"
            },
            {
                "table": "fort_sightings",
                "column": "is_ex_raid_eligible",
                "ctype": "tinyint(1) NULL"
            },
            {
                "table": "sightings",
                "column": "height",
                "ctype": "float NULL"
            },
            {
                "table": "pokestops",
                "column": "incident_start",
                "ctype": "int(11) NULL"
            },
            {
                "table": "pokestops",
                "column": "incident_expiration",
                "ctype": "int(11) NULL"
            },            {
                "table": "pokestops",
                "column": "last_modified",
                "ctype": "int(11) NULL"
            },
        ]

        for field in fields:
            self._check_create_column(field)

    def auto_hatch_eggs(self):
        logger.info("MonocleWrapper::auto_hatch_eggs called")

        mon_id = self.application_args.auto_hatch_number

        if mon_id == 0:
            logger.warning('You have enabled auto hatch but not the mon_id '
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
        logger.debug("Rows that need updating: {0}".format(
            rows_that_need_hatch_count))

        if rows_that_need_hatch_count > 0:
            counter = 0
            query = (
                "UPDATE raids "
                "SET pokemon_id = %s "
                "WHERE id = %s"
            )

            for row in res:
                logger.debug(row)
                vals = (
                    mon_id, row[0]
                )
                affected_rows = self.execute(query, vals, commit=True)

                if affected_rows == 1:
                    counter = counter + 1
                elif affected_rows > 1:
                    logger.error('Something is wrong with the indexing on your table you raids on this id {0}'
                                 .format(row[0]))
                else:
                    logger.error('The row we wanted to update did not get updated that had id {0}'
                                 .format(row[0]))

            if counter == rows_that_need_hatch_count:
                logger.info("{0} gym(s) were updated as part of the regular level 5 egg hatching checks"
                            .format(counter))
            else:
                logger.warning(
                    'There was an issue and the number expected the hatch did not match the successful updates. '
                    'Expected {0} Actual {1}'.format(rows_that_need_hatch_count, counter))
        else:
            logger.info('No Eggs due for hatching')

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
                logger.warning("lat or lng is none")
                continue
            elif geofence_helper and not geofence_helper.is_coord_inside_include_geofence([lat, lon]):
                logger.debug(
                    "Excluded hatch at {}, {} since the coordinate is not inside the given include fences", str(lat), str(lon))
                continue
            # timestamp = self.dbTimeStringToUnixTimestamp(str(start))
            data.append((time_battle + delay_after_hatch, Location(lat, lon)))

        logger.debug("Latest Q: {}", str(data))
        return data

    def submit_raid(self, gym, pkm, lvl, start, end, type, raid_no, capture_time, unique_hash="123",
                    MonWithNoEgg=False):
        logger.debug("[Crop: {} ({})] submit_raid: Submitting raid",
                     str(raid_no), str(unique_hash))

        wh_send = False
        wh_start = 0
        wh_end = 0
        egg_hatched = False

        logger.debug("[Crop: {} ({})] submit_raid: Submitting something of type {}", str(
            raid_no), str(unique_hash), str(type))

        logger.info("Submitting gym: {}, lv: {}, start and spawn: {}, end: {}, mon: {}",
                    gym, lvl, start, end, pkm)

        # always insert timestamp to last_scanned to have rows change if raid has been reported before

        if MonWithNoEgg:
            start = end - (int(self.application_args.raid_time) * 60)
            query = (
                "UPDATE raids "
                "SET level = %s, time_spawn = %s, time_battle = %s, time_end = %s, "
                "pokemon_id = %s, last_updated = %s "
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
            logger.info(
                "Updating without end- or starttime - we should've seen the egg before")
            query = (
                "UPDATE raids "
                "SET level = %s, pokemon_id = %s, last_updated = %s "
                "WHERE fort_id = %s AND time_end >= %s"
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
            logger.info("Updating everything")
            query = (
                "UPDATE raids "
                "SET level = %s, time_spawn = %s, time_battle = %s, time_end = %s, "
                "pokemon_id = %s, last_updated = %s "
                "WHERE fort_id = %s AND time_end >= %s"

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
                logger.info("Inserting mon without egg")
                start = end - 45 * 60
                query = (
                    "INSERT INTO raids (fort_id, level, time_spawn, time_battle, time_end, "
                    "pokemon_id) "
                    "VALUES(%s, %s, %s, %s, %s, %s)"
                )
                vals = (
                    gym, lvl, int(float(capture_time)
                                  ), start, end, pkm
                )
            elif end is None or start is None:
                logger.info("Inserting without end or start")
                # no end or start time given, just inserting won't help much...
                logger.warning("Useless to insert without endtime...")
                return False
            else:
                # we have start and end, mon is either with egg or we're submitting an egg
                logger.info("Inserting everything")
                query = (
                    "INSERT INTO raids (fort_id, level, time_spawn, time_battle, time_end, "
                    "pokemon_id, last_updated) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s)"

                )
                vals = (gym, lvl, int(float(capture_time)),
                        start, end, pkm)

            self.execute(query, vals, commit=True)

            wh_send = True
            if MonWithNoEgg:
                wh_start = int(end) - 2700
            else:
                wh_start = start
            wh_end = end
            if pkm is None:
                pkm = 0

        logger.info("[Crop: {} ({})] submit_raid: Submit finished",
                    str(raid_no), str(unique_hash))
        self.refresh_times(gym, raid_no, capture_time)

        return True

    def read_raid_endtime(self, gym, raid_no, unique_hash="123"):
        logger.debug("[Crop: {} ({})] read_raid_endtime: Check DB for existing mon", str(
            raid_no), str(unique_hash))
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
            logger.debug("[Crop: {} ({})] read_raid_endtime: Found Rows: {}", str(
                raid_no), str(unique_hash), str(number_of_rows))
            logger.info("[Crop: {} ({})] read_raid_endtime: Endtime already submitted", str(
                raid_no), str(unique_hash))
            return True
        else:
            logger.info("[Crop: {} ({})] read_raid_endtime: Endtime is new", str(
                raid_no), str(unique_hash))
            return False

    def get_raid_endtime(self, gym, raid_no, unique_hash="123"):
        logger.debug("[Crop: {} ({})] get_raid_endtime: Check DB for existing mon", str(
            raid_no), str(unique_hash))

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
                logger.debug("[Crop: {} ({})] get_raid_endtime: Returning found endtime", str(
                    raid_no), str(unique_hash))
                logger.debug("[Crop: {} ({})] get_raid_endtime: Time: {}", str(
                    raid_no), str(unique_hash), str(row[0]))

                return True, row[0]

        logger.debug("[Crop: {} ({})] get_raid_endtime: No matching endtime found", str(
            raid_no), str(unique_hash))
        return False, None

    def raid_exist(self, gym, type, raid_no, unique_hash="123", mon=0):
        logger.debug("[Crop: {} ({})] raid_exist: Check DB for existing entry", str(
            raid_no), str(unique_hash))
        now = time.time()

        # TODO: consider reducing the code...

        if type == "EGG":
            logger.debug("[Crop: {} ({})] raid_exist: Check for EGG", str(
                raid_no), str(unique_hash))
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
                logger.debug("[Crop: {} ({})] raid_exist: Found Rows: {}", str(
                    raid_no), str(unique_hash), str(number_of_rows))
                logger.info("[Crop: {} ({})] raid_exist: Egg already submitted", str(
                    raid_no), str(unique_hash))
                return True
            else:
                logger.info("[Crop: {} ({})] raid_exist: Egg is new",
                            str(raid_no), str(unique_hash))
                return False
        else:
            logger.debug("[Crop: {} ({})] raid_exist: Check for EGG", str(
                raid_no), str(unique_hash))
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
                logger.debug("[Crop: {} ({})] raid_exist: Found Rows: {}", str(
                    raid_no), str(unique_hash), str(number_of_rows))
                logger.info("[Crop: {} ({})] raid_exist: Mon already submitted", str(
                    raid_no), str(unique_hash))
                return True
            else:
                logger.info("[Crop: {} ({})] raid_exist: Mon is new",
                            str(raid_no), str(unique_hash))
                return False

    def refresh_times(self, gym, raid_no, capture_time, unique_hash="123"):
        logger.debug("[Crop: {} ({})] raid_exist: Check for EGG",
                     str(raid_no), str(unique_hash))
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
            "AS distance, forts.lat, forts.lon, forts.name, forts.name, forts.url "
            "FROM forts "
            "HAVING distance <= %s OR distance IS NULL "
            "ORDER BY distance"
        )
        vals = (
            float(lat), float(lng), float(lat), float(dist)
        )
        data = []
        res = self.execute(query, vals)

        for (id, distance, latitude, longitude, name, description, url) in res:
            data.append([id, distance, latitude, longitude, name, description, url])
        logger.debug("{MonocleWrapper::get_near_gyms} done")
        return data

    def set_scanned_location(self, lat, lng, capture_time):
        logger.debug(
            "MonocleWrapper::set_scanned_location: Scanned location not supported with monocle")
        pass

    def download_gym_images(self):
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
                filename = url_image_path + '_' + str(id) + '_.jpg'
                self.__download_img(str(url), str(filename))

        logger.info('Finished downloading gym images...')

        return True

    def get_gym_infos(self, id=False):
        gyminfo = {}

        query = (
            "SELECT forts.id, forts.lat, forts.lon, forts.name, forts.url, "
            "IFNULL(forts.park, 'unknown'), IFNULL(forts.sponsor,0), "
            "IFNULL(fort_sightings.team, 0) "
            "FROM forts "
            "LEFT JOIN fort_sightings ON forts.id = fort_sightings.fort_id "
            "WHERE forts.external_id IS NOT NULL "
        )

        res = self.execute(query)

        for (id, lat, lon, name, url, park, sponsor, team) in res:
            gyminfo[str(id)] = self.__encode_hash_json(id,
                                                       team,
                                                       float(lat),
                                                       float(lon),
                                                       str(name).replace('"', '\\"')
                                                       .replace('\n', '\\n'), str(url), park, sponsor)
        return gyminfo

    def gyms_from_db(self, geofence_helper):
        logger.info('Downloading gym coords from DB')

        query = (
            "SELECT lat, lon "
            "FROM forts"
        )

        res = self.execute(query)
        list_of_coords: List[Location] = []
        for (lat, lon) in res:
            list_of_coords.append(Location(lat, lon))

        if geofence_helper is not None:
            geofenced_coords = geofence_helper.get_geofenced_coordinates(
                list_of_coords)
            return geofenced_coords
        else:
            # import numpy as np
            # to_return = np.zeros(shape=(len(list_of_coords), 2))
            # for i in range(len(to_return)):
            #     to_return[i][0] = list_of_coords[i][0]
            #     to_return[i][1] = list_of_coords[i][1]
            return list_of_coords

    def update_encounters_from_db(self, geofence_helper, latest=0):
        logger.debug("monocleWrapper::update_encounters_from_db called")
        if geofence_helper is None:
            logger.error("No geofence_helper! Not fetching encounters.")
            return 0, {}

        logger.debug("Filtering with rectangle")
        rectangle = geofence_helper.get_polygon_from_fence()
        query = (
            "SELECT lat, lon, encounter_id, "
            "(expire_timestamp + (60 * 60)), "
            "updated "
            "FROM sightings "
            "WHERE "
            "lat >= %s AND lon >= %s AND "
            "lat <= %s AND lon <= %s AND "
            "cp IS NOT NULL AND "
            "expire_timestamp + (60 * 60) > UNIX_TIMESTAMP(NOW()) AND "
            "updated > %s "
        )

        params = rectangle
        params = params + (latest, )
        res = self.execute(query, params)
        list_of_coords = []
        for (latitude, longitude, encounter_id, disappear_time, last_modified) in res:
            list_of_coords.append(
                [latitude, longitude, encounter_id, disappear_time, last_modified])
            latest = max(latest, last_modified)

        encounter_id_coords = geofence_helper.get_geofenced_coordinates(
            list_of_coords)
        logger.debug("Got {} encounter coordinates within this rect and age (minLat, minLon, "
                     "maxLat, maxLon, last_modified): {}", len(encounter_id_coords), str(params))
        encounter_id_infos = {}
        for (latitude, longitude, encounter_id, disappear_time, last_modified) in encounter_id_coords:
            encounter_id_infos[encounter_id] = disappear_time
        return latest, encounter_id_infos

    def stops_from_db(self, geofence_helper):
        logger.info('Downloading pokestop coords from DB')

        minLat, minLon, maxLat, maxLon = geofence_helper.get_polygon_from_fence()

        query = (
            "SELECT lat, lon "
            "FROM pokestops "
            "WHERE (lat >= {} AND lon >= {} "
            "AND lat <= {} AND lon <= {}) "
        ).format(minLat, minLon, maxLat, maxLon)

        res = self.execute(query)
        list_of_coords: List[Location] = []
        for (lat, lon) in res:
            list_of_coords.append(Location(lat, lon))

        if geofence_helper is not None:
            geofenced_coords = geofence_helper.get_geofenced_coordinates(
                list_of_coords)
            return geofenced_coords
        else:
            # import numpy as np
            # to_return = np.zeros(shape=(len(list_of_coords), 2))
            # for i in range(len(to_return)):
            #     to_return[i][0] = list_of_coords[i][0]
            #     to_return[i][1] = list_of_coords[i][1]
            return list_of_coords

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

    def submit_mon_iv(self, origin: str, timestamp: float, encounter_proto: dict, mitm_mapper):
        logger.debug("Updating IV sent by {}", str(origin))
        wild_pokemon = encounter_proto.get("wild_pokemon", None)
        if wild_pokemon is None:
            return

        query_insert = (
            "INSERT sightings (pokemon_id, spawn_id, expire_timestamp, encounter_id, "
            "lat, lon, updated, gender, form, costume, weather_boosted_condition, weather_cell_id, "
            "atk_iv, def_iv, sta_iv, move_1, move_2, cp, level, weight, height) "
            "VALUES(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
            "ON DUPLICATE KEY UPDATE updated=VALUES(updated), atk_iv=VALUES(atk_iv), def_iv=VALUES(def_iv), "
            "sta_iv=VALUES(sta_iv), move_1=VALUES(move_1), move_2=VALUES(move_2), cp=VALUES(cp), "
            "level=VALUES(level), weight=VALUES(weight), costume=VALUES(costume), height=VALUES(height), "
            "weather_boosted_condition=VALUES(weather_boosted_condition), form=VALUES(form), "
            "gender=VALUES(gender), pokemon_id=VALUES(pokemon_id)"
        )

        encounter_id = wild_pokemon['encounter_id']
        if encounter_id < 0:
            encounter_id = encounter_id + 2 ** 64


        latitude = wild_pokemon.get("latitude")
        longitude = wild_pokemon.get("longitude")
        pokemon_data = wild_pokemon.get("pokemon_data")
        shiny = wild_pokemon['pokemon_data']['display']['is_shiny']

        mitm_mapper.collect_mon_iv_stats(origin, str(encounter_id), shiny)

        if pokemon_data.get("cp_multiplier") < 0.734:
            pokemon_level = (58.35178527 * pokemon_data.get("cp_multiplier") * pokemon_data.get("cp_multiplier") -
                             2.838007664 * pokemon_data.get("cp_multiplier") + 0.8539209906)
        else:
            pokemon_level = 171.0112688 * \
                pokemon_data.get("cp_multiplier") - 95.20425243

            pokemon_level = round(pokemon_level) * 2 / 2

        pokemon_display = pokemon_data.get("display")
        if pokemon_display is None:
            pokemon_display = {}

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

        if init:
            logger.debug("{0}: adding IV mon #{1} at {2}, {3}. Despawning at {4} (init)".format(
                str(origin),
                pokemon_data["id"],
                latitude, longitude,
                despawn_time))
        else:
            logger.debug("{0}: adding IV mon #{1} at {2}, {3}. Despawning at {4} (non-init)".format(
                str(origin),
                pokemon_data["id"],
                latitude, longitude,
                despawn_time))

        s2_weather_cell_id = S2Helper.lat_lng_to_cell_id(
            latitude, longitude, level=10)
        vals = (
            pokemon_data["id"],
            int(wild_pokemon.get("spawnpoint_id"), 16),
            despawn_time_unix,
            encounter_id,
            latitude, longitude, timestamp,
            pokemon_display.get("gender_value", None),
            pokemon_display.get("form_value", None),
            pokemon_display.get("costume_value", None),
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
            pokemon_data.get("height"),
        )
        self.execute(query_insert, vals, commit=True)

    def submit_mons_map_proto(self, origin: str, map_proto: dict, mon_ids_iv: Optional[List[int]], mitm_mapper):
        cells = map_proto.get("cells", None)
        if cells is None:
            return False
        query_mons_insert = (
            "INSERT IGNORE INTO sightings (pokemon_id, spawn_id, expire_timestamp, encounter_id, "
            "lat, lon, updated, gender, form, weather_boosted_condition, costume, weather_cell_id) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
        )

        mon_vals_insert = []

        for cell in cells:
            for wild_mon in cell['wild_pokemon']:
                spawnid = int(str(wild_mon['spawnpoint_id']), 16)
                lat = wild_mon['latitude']
                lon = wild_mon['longitude']
                now = int(time.time())
                encounter_id = wild_mon['encounter_id']
                if encounter_id < 0:
                    encounter_id = encounter_id + 2 ** 64

                mitm_mapper.collect_mon_stats(origin, str(encounter_id))

                s2_weather_cell_id = S2Helper.lat_lng_to_cell_id(
                    lat, lon, level=10)
                getdetspawntime = self.get_detected_endtime(str(spawnid))

                if getdetspawntime:
                    despawn_time = self._gen_endtime(getdetspawntime)
                    despawn_time_unix = despawn_time
                    logger.debug("{0}: adding mon (#{1}) at {2}, {3}. Despawns at {4} (non-init)", str(
                        origin), wild_mon['pokemon_data']['id'], lat, lon, despawn_time)
                else:
                    despawn_time = datetime.now() + timedelta(seconds=300)
                    despawn_time_unix = int(
                        time.mktime(despawn_time.timetuple()))
                    logger.debug("{0}: adding mon (#{1}) at {2}, {3}. Despaws at {4} (init)", str(
                        origin), wild_mon['pokemon_data']['id'], lat, lon, despawn_time)

                mon_id = wild_mon['pokemon_data']['id']

                mon_vals_insert.append(
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
                        wild_mon['pokemon_data']['display']['costume_value'],
                        s2_weather_cell_id
                    )
                )

        self.executemany(query_mons_insert, mon_vals_insert, commit=True)
        return True

    def submit_pokestops_map_proto(self, origin, map_proto):
        logger.debug("Inserting/Updating pokestops sent by {}", str(origin))
        cells = map_proto.get("cells", None)
        if cells is None:
            return False

        query_pokestops = (
            "INSERT INTO pokestops (external_id, lat, lon, name, url, updated, expires, last_modified, "
            "incident_start, incident_expiration) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
            "ON DUPLICATE KEY UPDATE updated=VALUES(updated), expires=VALUES(expires), "
            "lat=VALUES(lat), lon=VALUES(lon), last_modified=VALUES(last_modified), incident_start=VALUES(incident_start), "
            "incident_expiration=VALUES(incident_expiration)"
        )

        list_of_pokestops = []

        for cell in cells:
            for fort in cell['forts']:
                if fort['type'] == 1:

                    list_of_stops_vals = self.__extract_args_single_pokestop(
                        fort)

                    external_id = list_of_stops_vals[0]

                    list_of_pokestops.append((external_id, list_of_stops_vals[1],
                                              list_of_stops_vals[2], list_of_stops_vals[3],
                                              list_of_stops_vals[4], list_of_stops_vals[5],
                                              list_of_stops_vals[6], list_of_stops_vals[7],
                                              list_of_stops_vals[8], list_of_stops_vals[9]))

        self.executemany(query_pokestops, list_of_pokestops, commit=True)

        return True

    def submit_gyms_map_proto(self, origin, map_proto):
        logger.debug("Inserting/Updating gyms sent by {}", str(origin))
        cells = map_proto.get("cells", None)
        if cells is None:
            return False

        now = int(time.time())
        vals_forts = []
        vals_fort_sightings = []

        query_forts = (
            "INSERT IGNORE INTO forts (external_id, lat, lon, name, url, "
            "sponsor, weather_cell_id, parkid, park) "
            "VALUES(%s, %s, %s, %s, %s, %s, %s, %s, %s)"
        )

        query_fort_sightings = (
            "INSERT INTO fort_sightings (fort_id, last_modified, team, guard_pokemon_id, "
            "slots_available, is_in_battle, updated, is_ex_raid_eligible) "
            "VALUES ((SELECT id FROM forts WHERE external_id = %s), %s, %s, %s, %s, %s, %s, %s)"
            "ON DUPLICATE KEY UPDATE  last_modified=VALUES(last_modified), team=VALUES(team),"
            "guard_pokemon_id=VALUES(guard_pokemon_id),slots_available=VALUES(slots_available),"
            "is_in_battle=VALUES(is_in_battle), updated=VALUES(updated), "
            "is_ex_raid_eligible=VALUES(is_ex_raid_eligible)"
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
                    last_modified = gym['last_modified_timestamp_ms']/1000
                    is_ex_raid_eligible = gym['gym_details']['is_ex_raid_eligible']

                    if is_in_battle:
                        is_in_battle = 1
                    else:
                        is_in_battle = 0

                    vals_forts.append(
                        (
                            gym_id, lat, lon, None, image_uri, None, s2_cell_id, None, None
                        )
                    )

                    vals_fort_sightings.append(
                        (
                            gym_id, last_modified, team, guardmon, slots,
                            is_in_battle, now, is_ex_raid_eligible
                        )
                    )

        self.executemany(query_forts, vals_forts, commit=True)
        self.executemany(query_fort_sightings,
                         vals_fort_sightings, commit=True)
        return True

    def submit_gym_proto(self, origin, map_proto):
        logger.debug("Updating gym sent by {}", str(origin))
        if map_proto.get("result", 0) != 1:
            return False
        status = map_proto.get("gym_status_and_defenders", None)
        if status is None:
            return False
        fort_proto = status.get("pokemon_fort_proto", None)
        if fort_proto is None:
            return False
        gym_id = fort_proto["id"]
        name = map_proto["name"]
        url = map_proto["url"]

        set_keys = []
        vals = []

        if name is not None and name != "":
            set_keys.append("name=%s")
            vals.append(name)
        if url is not None and url != "":
            set_keys.append("url=%s")
            vals.append(url)

        if len(set_keys) == 0:
            return False

        query = "UPDATE forts SET " + ",".join(set_keys) + " WHERE external_id = %s"
        vals.append(gym_id)

        self.execute((query), tuple(vals), commit=True)

        return True

    def submit_raids_map_proto(self, origin: str, map_proto: dict, mitm_mapper):
        cells = map_proto.get("cells", None)
        if cells is None:
            return False
        raid_vals = []
        query_raid = (
            "INSERT INTO raids (external_id, fort_id, level, pokemon_id, time_spawn, time_battle, "
            "time_end, cp, move_1, move_2, form, last_updated, is_exclusive, gender) "
            "VALUES( (SELECT id FROM forts WHERE forts.external_id=%s), "
            "(SELECT id FROM forts WHERE forts.external_id=%s), %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) "
            "ON DUPLICATE KEY UPDATE level=VALUES(level), pokemon_id=VALUES(pokemon_id), "
            "time_spawn=VALUES(time_spawn), time_battle=VALUES(time_battle), time_end=VALUES(time_end), "
            "cp=VALUES(cp), move_1=VALUES(move_1), move_2=VALUES(move_2), "
            "form=VALUES(form), last_updated=VALUES(last_updated), gender=VALUES(gender)"
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
                        gender = gym['gym_details']['raid_info']['raid_pokemon']['display']['gender_value']
                    else:
                        pokemon_id = None
                        cp = 0
                        move_1 = 1
                        move_2 = 2
                        form = None
                        gender = None

                    raidendSec = int(gym['gym_details']
                                     ['raid_info']['raid_end'] / 1000)
                    raidspawnSec = int(
                        gym['gym_details']['raid_info']['raid_spawn'] / 1000)
                    raidbattleSec = int(
                        gym['gym_details']['raid_info']['raid_battle'] / 1000)

                    is_exclusive = gym['gym_details']['raid_info']['is_exclusive']
                    level = gym['gym_details']['raid_info']['level']
                    gymid = gym['id']

                    mitm_mapper.collect_raid_stats(origin, gymid)

                    now = time.time()

                    logger.debug("{}: adding/Updating gym {} with level {} ending at {}",
                                str(origin), str(gymid), str(level), str(raidendSec))

                    raid_vals.append(
                        (
                            gymid,
                            gymid,
                            level,
                            pokemon_id,
                            raidspawnSec,
                            raidbattleSec,
                            raidendSec,
                            cp, move_1, move_2,
                            form,
                            int(now),
                            is_exclusive,
                            gender
                        )
                    )
        self.executemany(query_raid, raid_vals, commit=True)
        logger.debug("{}: done submitting raids", str(origin))
        return True

    def submit_weather_map_proto(self, origin, map_proto, received_timestamp):
        logger.debug("Inserting/updating weather sent by {}", str(origin))
        cells = map_proto.get("cells", None)
        if cells is None:
            return False

        query_weather = (
            "INSERT INTO weather (s2_cell_id, `condition`, alert_severity, warn, day, updated) "
            "VALUES (%s, %s, %s, %s, %s, %s)"
            "ON DUPLICATE KEY UPDATE `condition`=VALUES(`condition`), alert_severity=VALUES(alert_severity), "
            "warn=VALUES(warn), day=VALUES(day), updated=VALUES(updated)"
        )

        list_of_weather_vals = []
        list_of_weather = []

        for client_weather in map_proto['client_weather']:
            # lat, lng, alt = S2Helper.get_position_from_cell(weather_extract['cell_id'])
            time_of_day = map_proto.get("time_of_day_value", 0)
            list_of_weather_vals.append(
                self.__extract_args_single_weather(
                    client_weather, time_of_day, received_timestamp)
            )

        for weather_data in list_of_weather_vals:

            list_of_weather.append((weather_data[0], weather_data[1], weather_data[2],
                                    weather_data[3], weather_data[4], weather_data[5]))

        self.executemany(query_weather, list_of_weather, commit=True)
        return True

    def get_to_be_encountered(self, geofence_helper, min_time_left_seconds, eligible_mon_ids):
        if min_time_left_seconds is None or eligible_mon_ids is None:
            logger.warning("MonocleWrapper::get_to_be_encountered: Not returning any encounters since no time left or "
                           "eligible mon IDs specified")
            return []
        logger.debug("Getting mons to be encountered")
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
                logger.warning("lat or lng is none")
                continue
            elif geofence_helper and not geofence_helper.is_coord_inside_include_geofence([lat, lon]):
                logger.debug(
                    "Excluded encounter at {}, {} since the coordinate is not inside the given include fences", str(lat), str(lon))
                continue

            next_to_encounter.append(
                    (pokemon_id, Location(lat, lon), encounter_id)
            )

        # now filter by the order of eligible_mon_ids
        to_be_encountered = []
        i = 0
        for mon_prio in eligible_mon_ids:
            for mon in next_to_encounter:
                if mon_prio == mon[0]:
                    to_be_encountered.append(
                            (i, mon[1], mon[2])
                    )
            i += 1
        return to_be_encountered

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
                logger.info('Ctrl-C interrupted')
                sys.exit(1)
            except Exception:
                retry = retry + 1
                logger.info('Download error', url)
                if retry <= 5:
                    logger.info('retry:', retry)
                else:
                    logger.info('Failed to download after 5 retry')

    def __encode_hash_json(self, team_id, latitude, longitude, name, url, park, sponsor):
        gym_json = {'team_id': team_id, 'latitude': latitude, 'longitude': longitude, 'name': name, 'description': '',
                    'url': url, 'park': park}

        if sponsor is not None:
            gym_json['sponsor'] = sponsor
        else:
            gym_json['sponsor'] = 0

        return gym_json

    def __extract_args_single_pokestop(self, stop_data):
        if stop_data['type'] != 1:
            logger.warning("{} is not a pokestop", str(stop_data))
            return None

        now = time.time()
        lure = 0

        last_modified = int(stop_data['last_modified_timestamp_ms']/1000)

        if "pokestop_display" in stop_data:
            incident_start = None
            incident_expiration = None

            start_ms = stop_data["pokestop_display"]["incident_start_ms"]
            expiration_ms = stop_data["pokestop_display"]["incident_expiration_ms"]

            if start_ms > 0:
                incident_start = start_ms / 1000

            if expiration_ms > 0:
                incident_expiration = expiration_ms / 1000

        return (
            stop_data['id'], stop_data['latitude'], stop_data['longitude'], "unknown",
            stop_data['image_url'], now, lure, last_modified,
            incident_start, incident_expiration
        )

    def __extract_args_single_weather(self, client_weather_data, time_of_day, received_timestamp):
        cell_id = client_weather_data["cell_id"]
        # realLat, realLng = S2Helper.middle_of_cell(cell_id)

        # TODO: local vars
        display_weather_data = client_weather_data.get("display_weather", None)
        if display_weather_data is None:
            return None
        else:
            gameplay_weather = client_weather_data["gameplay_weather"]["gameplay_condition"]

        return (
            cell_id,
            gameplay_weather,
            0, 0,
            time_of_day,
            int(round(received_timestamp))
        )

    def check_stop_quest(self, latitude, longitude):
        logger.debug("MonocleWrapper::stops_from_db called")
        query = (
            "SELECT trs_quest.GUID from trs_quest inner join pokestops on pokestops.external_id = trs_quest.GUID "
            "where from_unixtime(trs_quest.quest_timestamp,'%Y-%m-%d') = "
            "date_format(DATE_ADD( now() , INTERVAL '-15' MINUTE ), '%Y-%m-%d') "
            "and pokestops.lat=%s and pokestops.lon=%s"
        )
        data = (latitude, longitude)

        res = self.execute(query, data)
        number_of_rows = len(res)
        if number_of_rows > 0:
            logger.debug('Pokestop has already a quest with CURDATE()')
            return True
        else:
            logger.debug('Pokestop has not a quest with CURDATE()')
            return False

    def stop_from_db_without_quests(self, geofence_helper, levelmode):
        logger.debug("MonocleWrapper::stop_from_db_without_quests called")

        minLat, minLon, maxLat, maxLon = geofence_helper.get_polygon_from_fence()

        query = (
            "SELECT pokestops.lat, pokestops.lon "
            "FROM pokestops left join trs_quest on "
            "pokestops.external_id = trs_quest.GUID "
            "WHERE (pokestops.lat >= {} AND pokestops.lon >= {} "
            "AND pokestops.lat <= {} AND pokestops.lon <= {}) "
        ).format(minLat, minLon, maxLat, maxLon)

        if not levelmode:
            query_addon = ("AND DATE(from_unixtime(trs_quest.quest_timestamp,'%Y-%m-%d')) <> CURDATE() "
                           "OR trs_quest.GUID IS NULL ")

            query = query + query_addon

        res = self.execute(query)
        list_of_coords = []
        for (latitude, longitude) in res:
            list_of_coords.append(Location(latitude, longitude))

        if geofence_helper is not None:
            geofenced_coords = geofence_helper.get_geofenced_coordinates(
                list_of_coords)
            return geofenced_coords
        else:
            return list_of_coords

    def quests_from_db(self, neLat=None, neLon=None, swLat=None, swLon=None, oNeLat=None, oNeLon=None, oSwLat=None, oSwLon=None, timestamp=None):
        logger.debug("MonocleWrapper::quests_from_db called")
        questinfo = {}

        query = (
            "SELECT pokestops.external_id, pokestops.lat, pokestops.lon, trs_quest.quest_type, "
            "trs_quest.quest_stardust, trs_quest.quest_pokemon_id, trs_quest.quest_reward_type, "
            "trs_quest.quest_item_id, trs_quest.quest_item_amount, pokestops.name, pokestops.url, "
            "trs_quest.quest_target, trs_quest.quest_condition, trs_quest.quest_timestamp, "
            "trs_quest.quest_task, trs_quest.quest_reward, trs_quest.quest_template "
            "FROM pokestops inner join trs_quest ON pokestops.external_id = trs_quest.GUID "
            "WHERE DATE(from_unixtime(trs_quest.quest_timestamp,'%Y-%m-%d')) = CURDATE() "
        )

        query_where = ""

        if neLat is not None and neLon is not None and swLat is not None and swLon is not None:
            oquery_where = (
                " AND (lat >= {} AND lon >= {} "
                " AND lat <= {} AND lon <= {}) "
            ).format(swLat, swLon, neLat, neLon)

            query_where = query_where + oquery_where

        if oNeLat is not None and oNeLon is not None and oSwLat is not None and oSwLon is not None:
            oquery_where = (
                " AND NOT (lat >= {} AND lon >= {} "
                " AND lat <= {} AND lon <= {}) "
            ).format(oSwLat, oSwLon, oNeLat, oNeLon)

            query_where = query_where + oquery_where
        elif timestamp is not None:
            oquery_where = " AND trs_quest.quest_timestamp >= {}".format(timestamp)
            query_where = query_where + oquery_where

        res = self.execute(query + query_where)

        for (pokestop_id, latitude, longitude, quest_type, quest_stardust, quest_pokemon_id, quest_reward_type,
             quest_item_id, quest_item_amount, name, image, quest_target, quest_condition,
             quest_timestamp, quest_task, quest_reward, quest_template) in res:
            mon = "%03d" % quest_pokemon_id
            questinfo[pokestop_id] = ({
                'pokestop_id': pokestop_id, 'latitude': latitude, 'longitude': longitude,
                'quest_type': quest_type, 'quest_stardust': quest_stardust,
                'quest_pokemon_id': mon,
                'quest_reward_type': quest_reward_type, 'quest_item_id': quest_item_id,
                'quest_item_amount': quest_item_amount, 'name': name, 'image': image,
                'quest_target': quest_target,
                'quest_condition': quest_condition, 'quest_timestamp': quest_timestamp,
                'task': quest_task, 'quest_reward': quest_reward, 'quest_template': quest_template})
        return questinfo

    def submit_pokestops_details_map_proto(self, map_proto):
        logger.debug(
            "MonocleWrapper::submit_pokestops_details_map_proto called")
        pokestop_args = []
        # now = datetime.utcfromtimestamp(time.time()).strftime("%Y-%m-%d %H:%M:%S")

        query_pokestops = (
            "UPDATE pokestops set name = %s, url= %s, updated = %s, lat = %s, lon = %s "
            "where external_id = %s"
        )

        pokestop_args = self.__extract_args_single_pokestop_details(map_proto)

        if pokestop_args is not None:
            self.execute(query_pokestops, pokestop_args, commit=True)
        return True

    def get_raids_changed_since(self, timestamp):
        query = (
            "SELECT forts.external_id, level, time_spawn, time_battle, time_end, "
            "pokemon_id, cp, move_1, move_2, last_updated, form, is_exclusive, name, url, "
            "lat, lon, team, weather.condition, is_ex_raid_eligible, gender "
            "FROM raids "
            "LEFT JOIN fort_sightings ON raids.fort_id = fort_sightings.fort_id "
            "LEFT JOIN forts ON raids.fort_id = forts.id "
            "LEFT JOIN weather ON forts.weather_cell_id = weather.s2_cell_id "
            "WHERE last_updated >= %s"
        )

        res = self.execute(query, (timestamp, ))
        ret = []

        for (gym_id, level, spawn, start, end, pokemon_id,
                cp, move_1, move_2, last_scanned, form, is_exclusive,
                name, url, latitude, longitude, team_id,
                weather_boosted_condition, is_ex_raid_eligible, gender) in res:
            ret.append({
                "gym_id": gym_id,
                "level": level,
                "spawn": spawn,
                "start": start,
                "end": end,
                "pokemon_id": pokemon_id,
                "cp": cp,
                "move_1": move_1,
                "move_2": move_2,
                "last_scanned": last_scanned,
                "form": form,
                "name": name,
                "url": url,
                "latitude": latitude,
                "longitude": longitude,
                "team_id": team_id,
                "weather_boosted_condition": weather_boosted_condition,
                "is_exclusive": is_exclusive,
                "is_ex_raid_eligible": is_ex_raid_eligible,
                "gender": gender
            })

        return ret

    def get_mon_changed_since(self, timestamp):
        query = (
            "SELECT encounter_id, spawn_id, pokemon_id, lat, lon, expire_timestamp, "
            "atk_iv, def_iv, sta_iv, move_1, move_2, cp, weight, height, gender, form, costume, "
            "weather_boosted_condition, updated, level, "
            "(trs_spawn.calc_endminsec IS NOT NULL) AS verified "
            "FROM sightings "
            "LEFT JOIN trs_spawn ON sightings.spawn_id = trs_spawn.spawnpoint "
            "WHERE updated >= %s"
        )

        res = self.execute(query, (timestamp, ))
        ret = []

        for (encounter_id, spawnpoint_id, pokemon_id, latitude,
                longitude, disappear_time, individual_attack,
                individual_defense, individual_stamina, move_1, move_2,
                cp, weight, height, gender, form, costume, weather_boosted_condition,
                last_modified, level, verified) in res:
            ret.append({
                "encounter_id": encounter_id,
                "pokemon_id": pokemon_id,
                "last_modified": last_modified,
                "spawnpoint_id": spawnpoint_id,
                "latitude": latitude,
                "longitude": longitude,
                "disappear_time": disappear_time,
                "individual_attack": individual_attack,
                "individual_defense": individual_defense,
                "individual_stamina": individual_stamina,
                "move_1": move_1,
                "move_2": move_2,
                "cp": cp,
                "gender": gender,
                "form": form,
                "costume": costume,
                "weight": weight,
                "height": height,
                "weather_boosted_condition": weather_boosted_condition,
                "level": level,
                "spawn_verified": verified == 1
            })

        return ret

    def get_quests_changed_since(self, timestamp):
        pass

    def get_weather_changed_since(self, timestamp):
        query = (
            "SELECT s2_cell_id, weather.condition, alert_severity, warn, day, updated "
            "FROM weather "
            "WHERE updated >= %s"
        )

        res = self.execute(query, (timestamp, ))
        ret = []

        for (s2_cell_id, condition, alert_severity, warn, day, updated) in res:
            ret.append({
                "s2_cell_id": s2_cell_id,
                "gameplay_weather": condition,
                "severity": alert_severity,
                "warn_weather": warn,
                "world_time": day,
                "last_updated": updated
            })

        return ret

    def get_gyms_changed_since(self, timestamp):
        query = (
            "SELECT name, url, external_id, team, guard_pokemon_id, slots_available, "
            "lat, lon, is_in_battle, updated, is_ex_raid_eligible "
            "FROM forts "
            "LEFT JOIN fort_sightings ON forts.id = fort_sightings.fort_id "
            "WHERE updated >= %s"
        )

        res = self.execute(query, (timestamp, ))
        ret = []

        for (name, url, external_id, team, guard_pokemon_id, slots_available,
                lat, lon, is_in_battle, updated, is_ex_raid_eligible) in res:
            # TODO Check if the update should be last_modified from protos
            ret.append({
                "gym_id": external_id,
                "team_id": team,
                "guard_pokemon_id": guard_pokemon_id,
                "slots_available": slots_available,
                "latitude": lat,
                "longitude": lon,
                "is_in_battle": is_in_battle,
                "last_modified": updated,
                "name": name,
                "url": url,
                "is_ex_raid_eligible": is_ex_raid_eligible
            })

        return ret

    def get_stops_changed_since(self, timestamp):
        # no lured support for monocle now!

        query = (
            "SELECT external_id, lat, lon, name, url, "
            "updated, expires, incident_start, incident_expiration, last_modified from pokestops  "
            "WHERE updated >= %s AND expires > %s OR "
            "incident_start IS NOT NULL"
        )

        logger.debug('Pokestop query for webhook {}'.format(query))

        res = self.execute(query, (timestamp, timestamp,))

        logger.debug('Pokestop result for webhook {}'.format(res))

        ret = []

        for (external_id, latitude, longitude, name, image,
                last_updated, lure_expiration, incident_start, incident_expiration, last_modified) in res:

            ret.append({
                'pokestop_id': external_id,
                'latitude': latitude,
                'longitude': longitude,
                'lure_expiration': lure_expiration,
                'name': name,
                'image': image,
                "last_updated": last_updated,
                "last_modified": last_modified,
                "incident_start": incident_start if incident_start is not None else None,
                "incident_expiration": incident_expiration if incident_expiration is not None else None
            })

        return ret

    def __extract_args_single_pokestop_details(self, stop_data):
        if stop_data.get('type', 999) != 1:
            return None
        image = stop_data.get('image_urls', None)
        name = stop_data.get('name', None)
        now = int(time.time())

        return name, image[0], now, stop_data['latitude'], stop_data['longitude'], stop_data['fort_id']

    def statistics_get_pokemon_count(self, minutes):
        logger.debug('Fetching pokemon spawns count from db')
        query_where = ''
        query_date = "unix_timestamp(DATE_FORMAT(FROM_UNIXTIME(timestamp_scan), '%y-%m-%d %k:00:00'))" \
                     "as timestamp"
        if minutes:
            minutes = datetime.now().replace(
                minute=0, second=0, microsecond=0) - timedelta(minutes=int(minutes))
            query_where = ' where FROM_UNIXTIME(timestamp_scan) > \'%s\' ' % str(
                minutes)

        query = (
            "SELECT  %s, count(DISTINCT type_id) as Count, if(CP is NULL, 0, 1) as IV FROM sightings join "
            "trs_stats_detect_raw on sightings.encounter_id=trs_stats_detect_raw.type_id %s "
            "group by IV, day(FROM_UNIXTIME(expire_timestamp)), hour(FROM_UNIXTIME(expire_timestamp)) "
            "order by timestamp" %
                (str(query_date), str(query_where))
        )

        res = self.execute(query)

        return res

    def get_pokemon_spawns(self, hours):
        logger.debug('Fetching pokemon spawns from db')
        query_where = ''
        if hours:
            zero = datetime.now()
            hours = calendar.timegm(zero.timetuple()) - hours*60*60
            query_where = ' where expire_timestamp > %s ' % str(hours)

        query = (
            "SELECT pokemon_id, count(pokemon_id) from sightings %s group by pokemon_id" % str(
                query_where)
        )

        res = self.execute(query)

        total = reduce(lambda x, y: x + y[1], res, 0)

        return {'pokemon': res, 'total': total}

    def statistics_get_gym_count(self):
        logger.debug('Fetching gym count from db')

        query = (
            "SELECT if (team=0, 'WHITE', if (team=1, 'BLUE', if (team=2, 'RED', 'YELLOW'))) "
            "as Color, count(team) as Count FROM `fort_sightings` group by team"

        )
        res = self.execute(query)

        return res

    def statistics_get_stop_quest(self):
        logger.debug('Fetching gym count from db')

        query = (
            "SELECT "
            "if(FROM_UNIXTIME(trs_quest.quest_timestamp, '%y-%m-%d') is NULL,'NO QUEST',"
            "FROM_UNIXTIME(trs_quest.quest_timestamp, '%y-%m-%d')) as Quest, "
            "count(pokestops.external_id) as Count FROM pokestops left join trs_quest "
            "on pokestops.external_id = trs_quest.GUID "
            "group by FROM_UNIXTIME(trs_quest.quest_timestamp, '%y-%m-%d')"

        )
        res = self.execute(query)

        return res

    def get_best_pokemon_spawns(self):
        logger.debug('Fetching best pokemon spawns from db')

        query = (
                "SELECT encounter_id, pokemon_id, updated, "
                "atk_iv, def_iv, sta_iv, level, cp FROM sightings "
                "WHERE atk_iv>14 and def_iv>14 and sta_iv>14 "
                "group by encounter_id order by updated desc limit 30"
        )

        res = self.execute(query)
        return res

    def delete_stop(self, latitude: float, longitude: float):
        logger.debug('Deleting stop from db')
        query = (
            "delete from pokestops where lat=%s and lon=%s"
        )
        del_vars = (latitude, longitude)
        self.execute(query, del_vars, commit=True)

    def get_gyms_in_rectangle(self, neLat, neLon, swLat, swLon, oNeLat=None, oNeLon=None, oSwLat=None, oSwLon=None, timestamp=None):
        gyms = {}

        # base query to fetch gyms
        query = (
            "SELECT forts.external_id, forts.lat, forts.lon, forts.name, "
            "forts.url, IFNULL(fort_sightings.team, 0), "
            "fort_sightings.last_modified, raids.level, raids.time_spawn, raids.time_battle, "
            "raids.time_end, raids.pokemon_id, raids.form, fort_sightings.updated "
            "FROM forts "
            "INNER JOIN fort_sightings ON forts.id = fort_sightings.fort_id "
            "LEFT JOIN raids ON raids.fort_id = forts.id "
        )

        # fetch gyms only in a certain rectangle
        query_where = (
            " WHERE (lat >= {} AND lon >= {} "
            " AND lat <= {} AND lon <= {}) "
        ).format(swLat, swLon, neLat, neLon)

        # but don't fetch gyms from a known rectangle
        if oNeLat is not None and oNeLon is not None and oSwLat is not None and oSwLon is not None:
            oquery_where = (
                " AND NOT (lat >= {} AND lon >= {} "
                " AND lat <= {} AND lon <= {}) "
            ).format(oSwLat, oSwLon, oNeLat, oNeLon)

            query_where = query_where + oquery_where

        # there's no old rectangle so check for a timestamp to send only updated stuff
        elif timestamp is not None:
            # TODO ish: until we don't show any other information like raids
            #          we can use last_modified, since that will give us actual
            #          changes like gym color change
            oquery_where = " AND last_modified >= {} ".format(timestamp)

            query_where = query_where + oquery_where

        res = self.execute(query + query_where)

        for (gym_id, latitude, longitude, name, url, team_id, last_updated,
                level, spawn, start, end, mon_id, form, last_scanned) in res:

            # check if we found a raid and if it's still active
            if end is None or time.time() > end:
                raid = None
            else:
                raid = {
                    "spawn": spawn,
                    "start": start,
                    "end": end,
                    "mon": mon_id,
                    "form": form,
                    "level": level
                }

            gyms[gym_id] = {
                "id": gym_id,
                "name": name,
                "url": url,
                "latitude": latitude,
                "longitude": longitude,
                "team_id": int(team_id),
                "last_updated": last_updated,
                "last_scanned": last_scanned,
                "raid": raid
            }

        return gyms

    def check_stop_quest_level(self, worker, latitude, longitude):
        logger.debug("RmWrapper::stops_from_db called")
        query = (
            "SELECT trs_stats_detect_raw.type_id "
            "from trs_stats_detect_raw inner join pokestops on pokestops.external_id = trs_stats_detect_raw.type_id "
            "where pokestops.lat=%s and pokestops.lon=%s and trs_stats_detect_raw.worker=%s"
        )
        data = (latitude, longitude, worker)

        res = self.execute(query, data)
        number_of_rows = len(res)
        if number_of_rows > 0:
            logger.debug('Pokestop already visited')
            return True
        else:
            logger.debug('Pokestop not visited till now')
            return False

    def get_mons_in_rectangle(self, neLat, neLon, swLat, swLon, oNeLat=None, oNeLon=None, oSwLat=None, oSwLon=None, timestamp=None):
        mons = []

        query = (
            "SELECT encounter_id, spawn_id, pokemon_id, lat, "
            "lon, expire_timestamp, atk_iv, def_iv, "
            "sta_iv, move_1, move_2, cp, weight, height, "
            "gender, form, costume, weather_boosted_condition, updated "
            "FROM sightings "
            "WHERE expire_timestamp > {}"
        ).format(time.time())

        query_where = (
            " AND (lat >= {} AND lon >= {} "
            " AND lat <= {} AND lon <= {}) "
        ).format(swLat, swLon, neLat, neLon)

        if oNeLat is not None and oNeLon is not None and oSwLat is not None and oSwLon is not None:
            oquery_where = (
                " AND NOT (lat >= {} AND lon >= {} "
                " AND lat <= {} AND lon <= {}) "
            ).format(oSwLat, oSwLon, oNeLat, oNeLon)

            query_where = query_where + oquery_where

        # there's no old rectangle so check for a timestamp to send only updated stuff
        elif timestamp is not None:
            oquery_where = " AND updated >= {} ".format(timestamp)

            query_where = query_where + oquery_where

        res = self.execute(query + query_where)

        for (encounter_id, spawnpoint_id, pokemon_id, latitude, longitude,
                disappear_time, individual_attack, individual_defense,
                individual_stamina, move_1, move_2, cp,
                weight, height, gender, form, costume,
                weather_boosted_condition, updated) in res:

            mons.append({
                "encounter_id": encounter_id,
                "spawnpoint_id": spawnpoint_id,
                "mon_id": pokemon_id,
                "latitude": latitude,
                "longitude": longitude,
                "disappear_time": disappear_time,
                "individual_attack": individual_attack,
                "individual_defense": individual_defense,
                "individual_stamina": individual_stamina,
                "move_1": move_1,
                "move_2": move_2,
                "cp": cp,
                "weight": weight,
                "height": height,
                "gender": gender,
                "form": form,
                "costume": costume,
                "weather_boosted_condition": weather_boosted_condition,
                "last_modified": updated
            })

        return mons

    def statistics_get_shiny_stats(self):
        logger.debug('Fetching shiny pokemon stats from db')

        query = (
            "SELECT (select count(encounter_id) from sightings inner join trs_stats_detect_raw on "
            "trs_stats_detect_raw.type_id=sightings.encounter_id where sightings.pokemon_id=a.pokemon_id and "
            "trs_stats_detect_raw.worker=b.worker and sightings.form=a.form), count(DISTINCT encounter_id), "
            "a.pokemon_id, b.worker, GROUP_CONCAT(DISTINCT encounter_id ORDER BY encounter_id DESC SEPARATOR '<br>'),"
            " a.form "
            "FROM sightings a left join trs_stats_detect_raw b on a.encounter_id=b.type_id where b.is_shiny=1 group by "
            "b.is_shiny, a.pokemon_id, a.form, b.worker order by a.pokemon_id"
        )

        res = self.execute(query)

        return res


