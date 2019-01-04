import shutil
import sys
import time

import requests

from db.dbWrapperBase import DbWrapperBase
import logging
from datetime import datetime, timedelta

from utils.collections import Location
from utils.s2Helper import S2Helper

log = logging.getLogger(__name__)


class RmWrapper(DbWrapperBase):
    def ensure_last_updated_column(self):
        log.info("{RmWrapper::ensure_last_updated_column} called, returning True since RM doesn't need it")
        return True

    def auto_hatch_eggs(self):
        log.debug("{RmWrapper::auto_hatch_eggs} called")
        now = (datetime.now())
        now_timezone = int(time.mktime(now.timetuple())) - (self.timezone * 60 * 60)

        mon_id = self.application_args.auto_hatch_number

        if mon_id == 0:
            log.warning('You have enabled auto hatch but not the mon_id '
                        'so it will mark them as zero so they will remain unhatched...')

        log.debug("Time used to find eggs: " + str(now))
        timecheck = now_timezone

        query_for_count = (
            "SELECT gym_id, UNIX_TIMESTAMP(start), UNIX_TIMESTAMP(end) "
            "FROM raid "
            "WHERE start <= FROM_UNIXTIME(%s) AND end >= FROM_UNIXTIME(%s) "
            "AND level = 5 AND IFNULL(pokemon_id, 0) = 0"
        )

        vals = (
            timecheck, timecheck
        )

        res = self.execute(query_for_count, vals)
        rows_that_need_hatch_count = len(res)
        log.debug("Rows that need updating: {0}".format(rows_that_need_hatch_count))

        if rows_that_need_hatch_count > 0:
            counter = 0
            query = (
                "UPDATE raid "
                "SET pokemon_id = %s "
                "WHERE gym_id = %s"
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
                        log.debug('Sending auto hatched raid for raid id {0}'.format(row[0]))
                        self.webhook_helper.send_raid_webhook(
                            row[0], 'MON', row[1], row[2], 5, mon_id
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
        try:
            dt = datetime.strptime(timestring, '%Y-%m-%d %H:%M:%S.%f')
        except ValueError:
            dt = datetime.strptime(timestring, '%Y-%m-%d %H:%M:%S')
        unixtime = (dt - datetime(1970, 1, 1)).total_seconds()
        return unixtime

    def get_next_raid_hatches(self, delay_after_hatch, geofence_helper=None):
        log.debug("{RmWrapper::get_next_raid_hatches} called")
        db_time_to_check = datetime.now() - timedelta(hours=self.timezone)

        query = (
            "SELECT start, latitude, longitude "
            "FROM raid "
            "LEFT JOIN gym ON raid.gym_id = gym.gym_id WHERE raid.end > %s AND raid.pokemon_id IS NULL"
        )
        vals = (
            db_time_to_check,
        )

        res = self.execute(query, vals)
        data = []
        for (start, latitude, longitude) in res:
            if latitude is None or longitude is None:
                log.warning("lat or lng is none")
                continue
            elif geofence_helper and not geofence_helper.is_coord_inside_include_geofence([latitude, longitude]):
                log.debug("Excluded hatch at %s, %s since the coordinate is not inside the given include fences"
                          % (str(latitude), str(longitude)))
                continue
            timestamp = self.db_timestring_to_unix_timestamp(str(start))
            data.append((timestamp + delay_after_hatch, Location(latitude, longitude)))

        log.debug("Latest Q: %s" % str(data))
        return data

    def submit_raid(self, gym, pkm, lvl, start, end, type, raid_no, capture_time, unique_hash="123",
                    mon_with_no_egg=False):
        log.debug("{RmWrapper::submit_raid} called")
        log.debug("[Crop: %s (%s) ] submit_raid: Submitting raid" % (str(raid_no), str(unique_hash)))

        if self.raid_exist(gym, type, raid_no, unique_hash=str(unique_hash), mon=pkm):
            self.refresh_times(gym, raid_no, capture_time)
            log.debug("[Crop: %s (%s) ] submit_raid: %s already submitted, ignoring"
                      % (str(raid_no), str(unique_hash), str(type)))
            log.debug("{RmWrapper::submit_raid} done")
            return False

        if start is not None:
            start -= self.timezone * 60 * 60

        if end is not None:
            end -= self.timezone * 60 * 60

        wh_send = False
        wh_start = 0
        wh_end = 0
        egg_hatched = False
        
        now_timezone = datetime.fromtimestamp(float(capture_time))
        now_timezone = time.mktime(now_timezone.timetuple()) - (self.timezone * 60 * 60)

        log.debug("[Crop: %s (%s) ] submit_raid: Submitting something of type %s"
                  % (str(raid_no), str(unique_hash), str(type)))

        log.info("Submitting gym: %s, lv: %s, start and spawn: %s, end: %s, mon: %s"
                 % (gym, lvl, start, end, pkm))

        # always insert timestamp to last_scanned to have rows change if raid has been reported before

        if mon_with_no_egg:
            start = end - (int(self.application_args.raid_time) * 60)
            query = (
                "UPDATE raid "
                "SET level = %s, spawn = FROM_UNIXTIME(%s), start = FROM_UNIXTIME(%s), end = FROM_UNIXTIME(%s), "
                "pokemon_id = %s, last_scanned = FROM_UNIXTIME(%s), cp = %s, "
                "move_1 = %s, move_2 = %s "
                "WHERE gym_id = %s"
            )
            vals = (
                lvl, now_timezone, start, end, pkm, int(time.time()), '999', '1', '1', gym
            )
            # send out a webhook - this case should only occur once...
            wh_send = True
            wh_start = start
            wh_end = end
        elif end is None or start is None:
            # no end or start time given, just update anything there is
            log.info("Updating without end- or starttime - we should've seen the egg before")
            query = (
                "UPDATE raid "
                "SET level = %s, pokemon_id = %s, last_scanned = FROM_UNIXTIME(%s), cp = %s, "
                "move_1 = %s, move_2 = %s "
                "WHERE gym_id = %s"
            )
            vals = (
                lvl, pkm, int(time.time()), '999', '1', '1', gym
            )
            found_end_time, end_time = self.get_raid_endtime(gym, raid_no, unique_hash=unique_hash)
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
                "UPDATE raid "
                "SET level = %s, spawn = FROM_UNIXTIME(%s), start = FROM_UNIXTIME(%s), end = FROM_UNIXTIME(%s), "
                "pokemon_id = %s, last_scanned = FROM_UNIXTIME(%s), cp = %s, "
                "move_1 = %s, move_2 = %s "
                "WHERE gym_id = %s"
            )
            vals = (
                lvl, now_timezone, start, end, pkm, int(time.time()), '999', '1', '1', gym
            )
            wh_send = True
            wh_start = start
            wh_end = end

        affected_rows = self.execute(query, vals, commit=True)

        if affected_rows == 0 and not egg_hatched:
            # we need to insert the raid...
            if mon_with_no_egg:
                # submit mon without egg info -> we have an endtime
                log.info("Inserting mon without egg")
                start = end - (int(self.application_args.raid_time) * 60)
                query = (
                    "INSERT INTO raid (gym_id, level, spawn, start, end, pokemon_id, last_scanned, cp, "
                    "move_1, move_2) "
                    "VALUES(%s, %s, FROM_UNIXTIME(%s), FROM_UNIXTIME(%s), FROM_UNIXTIME(%s), %s, "
                    "FROM_UNIXTIME(%s), 999, 1, 1"
                )
                vals = (
                    gym, lvl, now_timezone, start, end, pkm, int(time.time())
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
                    "INSERT INTO raid (gym_id, level, spawn, start, end, pokemon_id, last_scanned, cp, "
                    "move_1, move_2) "
                    "VALUES (%s, %s, FROM_UNIXTIME(%s), FROM_UNIXTIME(%s), FROM_UNIXTIME(%s), %s, "
                    "FROM_UNIXTIME(%s), 999, 1, 1"
                )
                vals = (gym, lvl, now_timezone, start, end, pkm, int(time.time()))

            self.execute(query, vals, commit=True)

            wh_send = True
            if mon_with_no_egg:
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
            log.info('[Crop: ' + str(raid_no) + ' (' + str(unique_hash) + ') ] ' + 'submitRaid: Send webhook')
            if wh_start:
                wh_start += (self.timezone * 60 * 60)
            if wh_end:
                wh_end += (self.timezone * 60 * 60)
            self.webhook_helper.send_raid_webhook(
                gym, 'RAID', wh_start, wh_end, lvl, pkm
            )
        log.debug("{RmWrapper::submit_raid} done")
        return True

    def read_raid_endtime(self, gym, raid_no, unique_hash="123"):
        log.debug("{RmWrapper::read_raid_endtime} called")
        log.debug("[Crop: %s (%s) ] read_raid_endtime: Check DB for existing mon"
                  % (str(raid_no), str(unique_hash)))
        now = (datetime.now() - timedelta(hours=self.timezone)).strftime("%Y-%m-%d %H:%M:%S")

        query = (
            "SELECT raid.end "
            "FROM raid "
            "WHERE STR_TO_DATE(raid.end, \'%Y-%m-%d %H:%i:%S\') >= "
            "STR_TO_DATE(%s, \'%Y-%m-%d %H:%i:%S\') AND gym_id = %s"
        )
        vals = (
            now, gym
        )

        res = self.execute(query, vals)
        number_of_rows = len(res)

        if number_of_rows > 0:
            for row in res:
                log.debug("[Crop: %s (%s) ] read_raid_endtime: Found Rows: %s"
                          % (str(raid_no), str(unique_hash), str(number_of_rows)))
                log.info("[Crop: %s (%s) ] read_raid_endtime: Endtime already submitted"
                         % (str(raid_no), str(unique_hash)))
                log.debug("{RmWrapper::read_raid_endtime} done")
                return True

        log.info("[Crop: %s (%s) ] read_raid_endtime: Endtime is new"
                 % (str(raid_no), str(unique_hash)))
        log.debug("{RmWrapper::read_raid_endtime} done")
        return False

    def get_raid_endtime(self, gym, raid_no, unique_hash="123"):
        log.debug("{RmWrapper::get_raid_endtime} called")
        log.debug("[Crop: %s (%s) ] get_raid_endtime: Check DB for existing mon"
                  % (str(raid_no), str(unique_hash)))

        now = (datetime.now() - timedelta(hours=self.timezone)).strftime("%Y-%m-%d %H:%M:%S")
        query = (
            "SELECT UNIX_TIMESTAMP(raid.end) "
            "FROM raid "
            "WHERE STR_TO_DATE(raid.end, \'%Y-%m-%d %H:%i:%S\') >= "
            "STR_TO_DATE(%s, \'%Y-%m-%d %H:%i:%S\') and gym_id = %s"
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
        log.debug("{RmWrapper::raid_exist} called")
        log.debug("[Crop: %s (%s) ] raid_exist: Check DB for existing entry"
                  % (str(raid_no), str(unique_hash)))
        now = (datetime.now() - timedelta(hours=self.timezone)).strftime(
            "%Y-%m-%d %H:%M:%S")

        # TODO: consider reducing the code...

        if type == "EGG":
            log.debug("[Crop: %s (%s) ] raid_exist: Check for EGG"
                      % (str(raid_no), str(unique_hash)))
            query = (
                "SELECT start "
                "FROM raid "
                "WHERE STR_TO_DATE(raid.start, \'%Y-%m-%d %H:%i:%S\') >= "
                "STR_TO_DATE(%s, \'%Y-%m-%d %H:%i:%S\') and gym_id = %s"
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
                log.debug("{RmWrapper::raid_exist} done")
                return True
            else:
                log.info("[Crop: %s (%s) ] raid_exist: Egg is new"
                         % (str(raid_no), str(unique_hash)))
                log.debug("{RmWrapper::raid_exist} done")
                return False
        else:
            log.debug("[Crop: %s (%s) ] raid_exist: Check for EGG"
                      % (str(raid_no), str(unique_hash)))
            query = (
                "SELECT start "
                "FROM raid "
                "WHERE STR_TO_DATE(raid.start, \'%Y-%m-%d %H:%i:%S\') <= "
                "STR_TO_DATE(%s, \'%Y-%m-%d %H:%i:%S\') AND "
                "STR_TO_DATE(raid.end, \'%Y-%m-%d %H:%i:%S\') >= "
                "STR_TO_DATE(%s, \'%Y-%m-%d %H:%i:%S\') "
                "AND gym_id = %s AND pokemon_id = %s"
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
                log.debug("{RmWrapper::raid_exist} done")
                return True
            else:
                log.info("[Crop: %s (%s) ] raid_exist: Mon is new"
                         % (str(raid_no), str(unique_hash)))
                log.debug("{RmWrapper::raid_exist} done")
                return False

    def refresh_times(self, gym, raid_no, capture_time, unique_hash="123"):
        log.debug("{RmWrapper::refresh_times} called")
        log.debug("[Crop: %s (%s) ] raid_exist: Check for EGG"
                  % (str(raid_no), str(unique_hash)))
        now = (datetime.fromtimestamp(float(capture_time)) - timedelta(
            hours=self.timezone)).strftime("%Y-%m-%d %H:%M:%S")
        now_timezone = datetime.fromtimestamp(float(capture_time))
        now_timezone = time.mktime(now_timezone.timetuple()) - (self.timezone * 60 * 60)

        query = (
            "UPDATE gym "
            "SET last_modified = %s, last_scanned = %s "
            "WHERE gym_id = %s"
        )
        vals = (
            now, now, gym
        )
        self.execute(query, vals, commit=True)

        query = (
            "UPDATE raid "
            "SET last_scanned = FROM_UNIXTIME(%s) "
            "WHERE gym_id = %s"
        )
        vals = (
            now_timezone, gym
        )
        self.execute(query, vals, commit=True)

    def get_near_gyms(self, lat, lng, hash, raid_no, dist, unique_hash="123"):
        log.debug("{RmWrapper::get_near_gyms} called")
        # if dist == 99:
        #     distance = str(9999)
        #     lat = self.application_args.home_lat
        #     lng = self.application_args.home_lng
        # else:
        #     distance = str(self.application_args.gym_scan_distance)

        #dist = float(dist) * 1000

        query = (
            "SELECT gym_id, "
            "( 6371 * "
            "acos( cos(radians(%s)) "
            "* cos(radians(latitude)) "
            "* cos(radians(longitude) - radians(%s)) "
            "+ sin(radians(%s)) "
            "* sin(radians(latitude))"
            ")"
            ") "
            "AS distance "
            "FROM gym "
            "HAVING distance <= %s "
            "OR distance IS NULL "
            "ORDER BY distance"
        )

        vals = (
            float(lat), float(lng), float(lat), float(dist)
        )
        data = []
        res = self.execute(query, vals)
        for (gym_id, distance) in res:
            data.append([gym_id, distance])
        log.debug("{RmWrapper::get_near_gyms} done")
        return data

    def set_scanned_location(self, lat, lng, capture_time):
        log.debug("{RmWrapper::set_scanned_location} called")
        now = datetime.utcfromtimestamp(time.time()).strftime('%Y-%m-%d %H:%M:%S')
        cell_id = int(S2Helper.lat_lng_to_cell_id(float(lat), float(lng), 16))
        query = (
            "INSERT INTO scannedlocation (cellid, latitude, longitude, last_modified, done, band1, band2, "
            "band3, band4, band5, midpoint, width) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) "
            "ON DUPLICATE KEY UPDATE last_modified=VALUES(last_modified)"
        )
        # TODO: think of a better "unique, real number"
        vals = (cell_id, lat, lng, now, -1, -1, -1, -1, -1, -1, -1, -1)
        self.execute(query, vals, commit=True)

        log.debug("{RmWrapper::set_scanned_location} Done setting location...")
        return True

    def download_gym_images(self):
        log.debug("{RmWrapper::download_gym_images} called")
        import json
        import io
        import os
        gyminfo = {}

        url_image_path = os.getcwd() + '/ocr/gym_img/'

        file_path = os.path.dirname(url_image_path)
        if not os.path.exists(file_path):
            os.makedirs(file_path)

        query = (
            "SELECT gym.gym_id, gym.team_id, gym.latitude, gym.longitude, gymdetails.name, "
            "gymdetails.description, gymdetails.url "
            "FROM gym INNER JOIN gymdetails "
            "WHERE gym.gym_id = gymdetails.gym_id"
        )

        res = self.execute(query)

        for (gym_id, team_id, latitude, longitude, name, description, url) in res:
            if url is not None:
                if not self.application_args.justjson:
                    filename = url_image_path + '_' + str(gym_id) + '_.jpg'
                    log.debug('Downloading', filename)
                    self.__download_img(str(url), str(filename))
                gyminfo[gym_id] = self.__encode_hash_json(team_id, latitude, longitude, name, description, url)

        with io.open('gym_info.json', 'w') as outfile:
            outfile.write(str(json.dumps(gyminfo, indent=4, sort_keys=True)))
        log.debug('Finished downloading gym images...')
        
        return True

    def get_gym_infos(self, id=False):
        log.debug("{RmWrapper::get_gym_infos} called")
        gyminfo = {}

        query = (
            "SELECT gym.gym_id, gym.latitude, gym.longitude, "
            "gymdetails.name, gymdetails.description, gymdetails.url, "
            "gym.team_id "
            "FROM gym INNER JOIN gymdetails "
            "WHERE gym.gym_id = gymdetails.gym_id"
        )

        res = self.execute(query)

        for (gym_id, latitude, longitude, name, description, url, team_id) in res:
            gyminfo[gym_id] = self.__encode_hash_json(team_id, latitude, longitude, name, description, url)
        return gyminfo

    def gyms_from_db(self, geofence_helper):
        log.debug("{RmWrapper::gyms_from_db} called")
        query = (
            "SELECT latitude, longitude "
            "FROM gym"
        )

        res = self.execute(query)
        list_of_coords = []
        for (latitude, longitude) in res:
            list_of_coords.append([latitude, longitude])

        if geofence_helper is not None:
            geofenced_coords = geofence_helper.get_geofenced_coordinates(list_of_coords)
            return geofenced_coords
        else:
            import numpy as np
            to_return = np.zeros(shape=(len(list_of_coords), 2))
            for i in range(len(to_return)):
                to_return[i][0] = list_of_coords[i][0]
                to_return[i][1] = list_of_coords[i][1]
            return to_return

    def stops_from_db(self, geofence_helper):
        log.debug("{RmWrapper::stops_from_db} called")

        query = (
            "SELECT latitude, longitude "
            "FROM pokestop"
        )

        res = self.execute(query)
        list_of_coords = []
        for (latitude, longitude) in res:
            list_of_coords.append([latitude, longitude])

        if geofence_helper is not None:
            geofenced_coords = geofence_helper.get_geofenced_coordinates(list_of_coords)
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
        log.debug("{RmWrapper::update_insert_weather} called")
        now_timezone = datetime.fromtimestamp(float(capture_time))
        now_timezone = time.mktime(now_timezone.timetuple()) - (self.timezone * 60 * 60)
        now = now = datetime.utcfromtimestamp(time.time()).strftime('%Y-%m-%d %H:%M:%S')

        real_lat, real_lng = S2Helper.middle_of_cell(cell_id)
        if weather_daytime == 2 and gameplay_weather == 3:
            gameplay_weather = 13

        # TODO: put severity and warn_weather properly
        query = 'INSERT INTO weather (s2_cell_id, latitude, longitude, cloud_level, rain_level, wind_level, ' \
                'snow_level, fog_level, wind_direction, gameplay_weather, severity, warn_weather, world_time, ' \
                'last_updated) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) ' \
                'ON DUPLICATE KEY UPDATE fog_level=%s, cloud_level=%s, snow_level=%s, wind_direction=%s, ' \
                'world_time=%s, latitude=%s, longitude=%s, gameplay_weather=%s, last_updated=%s'
        data = (cell_id, real_lat, real_lng, cloud_level, rain_level, wind_level, snow_level, fog_level,
                wind_direction, gameplay_weather, None, None, weather_daytime, str(now),
                fog_level, cloud_level, snow_level, wind_direction, weather_daytime, real_lat, real_lng,
                gameplay_weather, str(now))

        self.execute(query, data, commit=True)

        self.webhook_helper.send_weather_webhook(
            cell_id, gameplay_weather, 0, 0, weather_daytime, now_timezone
        )

    def submit_mon_iv(self, id, type, lat, lon, desptime, spawnid, gender, weather, costume, form, cp, move_1, move_2,
                      weight, height, individual_attack, individual_defense, individual_stamina, cpmulti):
        log.debug("{RmWrapper::submit_mon_iv} called")
        now = datetime.utcfromtimestamp(time.time()).strftime('%Y-%m-%d %H:%M:%S')
        despawn_time = datetime.now() + timedelta(seconds=300)
        despawn_time = datetime.utcfromtimestamp(
            time.mktime(despawn_time.timetuple())
        ).strftime('%Y-%m-%d %H:%M:%S')
        init = True

        getdetspawntime = self.get_detected_endtime(str(spawnid))

        if getdetspawntime:
            despawn_time = datetime.utcfromtimestamp(
                self._gen_endtime(getdetspawntime)
            ).strftime('%Y-%m-%d %H:%M:%S')
            init = False

        if init:
            log.info("Updating mon #{0} at {1}, {2}. Despawning at {3} (init)".format(id, lat, lon, despawn_time))
        else:
            log.info("Updating mon #{0} at {1}, {2}. Despawning at {3} (non-init)".format(id, lat, lon, despawn_time))

        query = (
            "UPDATE pokemon "
            "SET individual_attack = %s, individual_defense = %s, individual_stamina = %s, "
            "move_1 = %s, move_2 = %s, cp = %s, last_modified = %s, weight = %s, height = %s, "
            "cp_multiplier = %s, catch_prob_1 = %s, catch_prob_2 = %s, catch_prob_3 = %s, "
            "WHERE encounter_id = %s"
        )
        vals = (
            individual_attack, individual_defense, individual_stamina, move_1, move_2, cp,
            now, weight, height, cpmulti, 1, 1, 1, id
        )

        self.execute(query, vals, commit=True)

    def submit_mons_map_proto(self, map_proto):
        log.debug("{RmWrapper::submit_mons_map_proto} called")
        cells = map_proto.get("cells", None)
        if cells is None:
            return False
        query_mons = (
            "INSERT INTO pokemon (encounter_id, spawnpoint_id, pokemon_id, latitude, longitude, disappear_time, "
            "individual_attack, individual_defense, individual_stamina, move_1, move_2, cp, cp_multiplier, "
            "weight, height, gender, catch_prob_1, catch_prob_2, catch_prob_3, rating_attack, rating_defense, "
            "weather_boosted_condition, last_modified, costume, form) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, "
            "%s, %s, %s, %s, %s) "
            "ON DUPLICATE KEY UPDATE last_modified=VALUES(last_modified), disappear_time=VALUES(disappear_time)"
        )

        mon_args = []
        for cell in cells:
            for wild_mon in cell['wild_pokemon']:
                spawnid = int(str(wild_mon['spawnpoint_id']), 16)
                lat = wild_mon['latitude']
                lon = wild_mon['longitude']
                mon_id = wild_mon['pokemon_data']['id']

                now = datetime.utcfromtimestamp(time.time()).strftime('%Y-%m-%d %H:%M:%S')
                despawn_time = datetime.now() + timedelta(seconds=300)
                despawn_time = datetime.utcfromtimestamp(time.mktime(despawn_time.timetuple())).strftime(
                    '%Y-%m-%d %H:%M:%S')
                init = True

                getdetspawntime = self.get_detected_endtime(str(spawnid))
                if getdetspawntime:
                    despawn_time_unix = self._gen_endtime(getdetspawntime)
                else:
                    despawn_time_unix = int(time.time()) + 3 * 60

                if getdetspawntime:
                    despawn_time = datetime.utcfromtimestamp(despawn_time_unix).strftime('%Y-%m-%d %H:%M:%S')
                    init = False

                if init:
                    log.info("Adding mon with id #{0} at {1}, {2}. Despawning at {3} (init) ({4})"
                             .format(mon_id, lat, lon, despawn_time, spawnid))
                else:
                    log.info("Adding mon with id #{0} at {1}, {2}. Despawning at {3} (non-init) ({4})"
                             .format(mon_id, lat, lon, despawn_time, spawnid))

                self.webhook_helper.submit_pokemon_webhook(
                    str(abs(wild_mon['encounter_id'])), mon_id, int(time.time()),
                    spawnid, lat, lon, int(despawn_time_unix)
                )

                mon_args.append(
                    (
                        abs(wild_mon['encounter_id']), spawnid, mon_id, lat, lon,
                        despawn_time,
                        None, None, None, None, None, None, None, None, None,  # TODO: consider .get("XXX", None)
                        wild_mon['pokemon_data']['display']['gender_value'],
                        None, None, None, None, None,
                        wild_mon['pokemon_data']['display']['weather_boosted_value'],
                        now, wild_mon['pokemon_data']['display']['costume_value'],
                        wild_mon['pokemon_data']['display']['form_value']
                    )
                )

        self.executemany(query_mons, mon_args, commit=True)
        return True

    def submit_pokestops_map_proto(self, map_proto):
        log.debug("{RmWrapper::submit_pokestops_map_proto} called")
        cells = map_proto.get("cells", None)
        if cells is None:
            return False
        pokestop_args = []
        # now = datetime.datetime.utcfromtimestamp(time.time()).strftime("%Y-%m-%d %H:%M:%S")

        query_pokestops = (
            "INSERT INTO pokestop (pokestop_id, enabled, latitude, longitude, last_modified, lure_expiration, "
            "last_updated) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s) "
            "ON DUPLICATE KEY UPDATE last_updated=VALUES(last_updated), lure_expiration=VALUES(lure_expiration)"
        )

        for cell in cells:
            for fort in cell['forts']:
                if fort['type'] == 1:
                    pokestop_args.append(self.__extract_args_single_pokestop(fort))

        self.executemany(query_pokestops, pokestop_args, commit=True)
        return True

    def submit_gyms_map_proto(self, map_proto):
        log.debug("{RmWrapper::submit_gyms_map_proto} called")
        cells = map_proto.get("cells", None)
        if cells is None:
            return False
        gym_args = []
        gym_details_args = []
        now = datetime.utcfromtimestamp(time.time()).strftime("%Y-%m-%d %H:%M:%S")

        query_gym = (
            "INSERT INTO gym (gym_id, team_id, guard_pokemon_id, slots_available, enabled, latitude, longitude, "
            "total_cp, is_in_battle, last_modified, last_scanned) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) "
            "ON DUPLICATE KEY UPDATE "
            "guard_pokemon_id=VALUES(guard_pokemon_id), team_id=VALUES(team_id), "
            "slots_available=VALUES(slots_available), last_scanned=VALUES(last_scanned), "
            "last_modified=VALUES(last_modified)"
        )
        query_gym_details = (
            "INSERT INTO gymdetails (gym_id, name, url, last_scanned) "
            "VALUES (%s, %s, %s, %s) "
            "ON DUPLICATE KEY UPDATE last_scanned=VALUES(last_scanned)"
        )

        for cell in cells:
            for gym in cell['forts']:
                if gym['type'] == 0:
                    gym_args.append(
                        (
                            gym['id'], gym['gym_details']['owned_by_team'], gym['gym_details']['guard_pokemon'],
                            gym['gym_details']['slots_available'], 1, gym['latitude'], gym['longitude'],
                            0,  # total CP
                            0,  # is_in_battle
                            now, now
                        )
                    )

                    gym_details_args.append(
                        (
                            gym['id'], "unknown", gym['image_url'], now
                        )
                    )
        self.executemany(query_gym, gym_args, commit=True)
        self.executemany(query_gym_details, gym_details_args, commit=True)
        log.debug("submit_gyms done")
        return True

    def submit_raids_map_proto(self, map_proto):
        log.debug("{RmWrapper::submit_raids_map_proto} called")
        cells = map_proto.get("cells", None)
        if cells is None:
            return False
        raid_args = []
        now = datetime.utcfromtimestamp(time.time()).strftime("%Y-%m-%d %H:%M:%S")

        query_raid = (
            "INSERT INTO raid (gym_id, level, spawn, start, end, pokemon_id, cp, move_1, move_2, last_scanned) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) "
            "ON DUPLICATE KEY UPDATE level=VALUES(level), spawn=VALUES(spawn), start=VALUES(start), "
            "end=VALUES(end), pokemon_id=VALUES(pokemon_id), cp=VALUES(cp), move_1=VALUES(move_1), "
            "move_2=VALUES(move_2), last_scanned=VALUES(last_scanned)"
        )

        for cell in cells:
            for gym in cell['forts']:
                if gym['type'] == 0 and gym['gym_details']['has_raid']:
                    gym_has_raid = gym['gym_details']['raid_info']['has_pokemon']
                    if gym_has_raid:
                        pokemon_id = gym['gym_details']['raid_info']['pokemon']['id']
                        cp = gym['gym_details']['raid_info']['pokemon']['cp']
                        move_1 = gym['gym_details']['raid_info']['pokemon']['move_1']
                        move_2 = gym['gym_details']['raid_info']['pokemon']['move_2']
                    else:
                        pokemon_id = None
                        cp = 0
                        move_1 = 1
                        move_2 = 2

                    raidendSec = int(gym['gym_details']['raid_info']['raid_end'] / 1000)
                    raidspawnSec = int(gym['gym_details']['raid_info']['raid_spawn'] / 1000)
                    raidbattleSec = int(gym['gym_details']['raid_info']['raid_battle'] / 1000)

                    raidend_date = datetime.utcfromtimestamp(float(raidendSec)).strftime("%Y-%m-%d %H:%M:%S")
                    raidspawn_date = datetime.utcfromtimestamp(float(raidspawnSec)).strftime(
                        "%Y-%m-%d %H:%M:%S")
                    raidstart_date = datetime.utcfromtimestamp(float(raidbattleSec)).strftime(
                        "%Y-%m-%d %H:%M:%S")

                    level = gym['gym_details']['raid_info']['level']
                    gymid = gym['id']
                    team = gym['gym_details']['owned_by_team']

                    # TODO: get matching weather...
                    self.webhook_helper.send_raid_webhook(
                        gymid=gymid, type='RAID', start=raidbattleSec, end=raidendSec, lvl=level,
                        mon=pokemon_id, team_param=team, cp_param=cp, move1_param=move_1,
                        move2_param=move_2, lat_param=gym['latitude'], lng_param=gym['longitude'],
                        image_url=gym['image_url']
                    )

                    log.info("Adding/Updating gym at gym %s with level %s ending at %s"
                             % (str(gymid), str(level), str(raidend_date)))

                    raid_args.append(
                        (
                            gymid,
                            level,
                            raidspawn_date,
                            raidstart_date,
                            raidend_date,
                            pokemon_id, cp, move_1, move_2, now
                        )
                    )
        self.executemany(query_raid, raid_args, commit=True)
        log.debug("dbWrapper::submit_raids_map_proto: Done submitting raids")
        return True

    def submit_weather_map_proto(self, map_proto, received_timestamp):
        log.debug("{RmWrapper::submit_weather_map_proto} called")
        cells = map_proto.get("cells", None)
        if cells is None:
            return False

        query_weather = (
            "INSERT INTO weather (s2_cell_id, latitude, longitude, cloud_level, rain_level, wind_level, "
            "snow_level, fog_level, wind_direction, gameplay_weather, severity, warn_weather, world_time, "
            "last_updated) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) "
            "ON DUPLICATE KEY UPDATE fog_level=VALUES(fog_level), cloud_level=VALUES(cloud_level), "
            "snow_level=VALUES(snow_level), wind_direction=VALUES(wind_direction), "
            "world_time=VALUES(world_time), gameplay_weather=VALUES(gameplay_weather), "
            "last_updated=VALUES(last_updated)"
        )

        list_of_weather_args = []
        for client_weather in map_proto['client_weather']:
            # lat, lng, alt = S2Helper.get_position_from_cell(weather_extract['cell_id'])
            time_of_day = map_proto.get("time_of_day_value", 0)
            list_of_weather_args.append(
                self.__extract_args_single_weather(client_weather, time_of_day, received_timestamp)
            )
        self.executemany(query_weather, list_of_weather_args, commit=True)
        return True

    def __encode_hash_json(self, team_id, latitude, longitude, name, description, url):
        return (
            {'team_id': team_id, 'latitude': latitude, 'longitude': longitude, 'name': name, 'description': '',
             'url': url})

    def __download_img(self, url, file_name):
        retry = 1
        while retry <= 5:
            try:
                r = requests.get(url, stream=True, timeout=10)
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

    def __extract_args_single_pokestop(self, stop_data):
        if stop_data['type'] != 1:
            log.warning("%s is not a pokestop" % str(stop_data))
            return None
        lure = stop_data['lure_expires']
        now = datetime.utcfromtimestamp(time.time()).strftime("%Y-%m-%d %H:%M:%S")
        if lure > 0:
            lure = datetime.utcfromtimestamp(float(lure) / 1000).strftime("%Y-%m-%d %H:%M:%S")
        else:
            lure = '1970-01-01 00:00:00'
        return stop_data['id'], 1, stop_data['latitude'], stop_data['longitude'], now, lure, now

    def __extract_args_single_weather(self, client_weather_data, time_of_day, received_timestamp):
        now = datetime.utcfromtimestamp(time.time()).strftime('%Y-%m-%d %H:%M:%S')
        cell_id = client_weather_data["cell_id"]
        real_lat, real_lng = S2Helper.middle_of_cell(cell_id)

        display_weather_data = client_weather_data.get("display_weather", None)
        if display_weather_data is None:
            return None
        elif time_of_day == 2 and client_weather_data["gameplay_weather"]["gameplay_condition"] == 3:
            gameplay_weather = 13
        else:
            gameplay_weather = client_weather_data["gameplay_weather"]["gameplay_condition"]

        now_timezone = datetime.fromtimestamp(float(received_timestamp))
        now_timezone = time.mktime(now_timezone.timetuple()) - (self.timezone * 60 * 60)

        self.webhook_helper.send_weather_webhook(cell_id, gameplay_weather, 0, 0,
                                                 time_of_day, now_timezone)

        return (
            cell_id, real_lat, real_lng,
            display_weather_data.get("cloud_level", 0),
            display_weather_data.get("rain_level", 0),
            display_weather_data.get("wind_level", 0),
            display_weather_data.get("snow_level", 0),
            display_weather_data.get("fog_level", 0),
            display_weather_data.get("wind_direction", 0),
            gameplay_weather,
            # TODO: alerts
            0, 0,
            time_of_day, now
        )
