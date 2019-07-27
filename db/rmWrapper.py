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
from utils.gamemechanicutil import gen_despawn_timestamp
from utils.logging import logger
from utils.s2Helper import S2Helper


class RmWrapperManager(SyncManager):
    pass


class RmWrapper(DbWrapperBase):

    def __init__(self, args):
        super().__init__(args)

        self.__ensure_columns_exist()

    def __ensure_columns_exist(self):
        fields = [
            {
                "table": "raid",
                "column": "is_exclusive",
                "ctype": "tinyint(1) NULL"
            },
            {
                "table": "raid",
                "column": "gender",
                "ctype": "tinyint(1) NULL"
            },
            {
                "table": "gym",
                "column": "is_ex_raid_eligible",
                "ctype": "tinyint(1) NOT NULL DEFAULT '0'"
            },
            {
                "table": "pokestop",
                "column": "incident_start",
                "ctype": "datetime NULL"
            },
            {
                "table": "pokestop",
                "column": "incident_expiration",
                "ctype": "datetime NULL"
            }
        ]

        for field in fields:
            self._check_create_column(field)

    def auto_hatch_eggs(self):
        logger.debug("RmWrapper::auto_hatch_eggs called")
        now = (datetime.now())
        now_timestamp = time.mktime(datetime.utcfromtimestamp(
            float(time.time())).timetuple())

        mon_id = self.application_args.auto_hatch_number

        if mon_id == 0:
            logger.warning("You have enabled auto hatch but not the mon_id "
                           "so it will mark them as zero so they will remain unhatched...")

        logger.debug("Time used to find eggs: " + str(now))
        timecheck = now_timestamp

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
        logger.debug("Rows that need updating: {}".format(
            rows_that_need_hatch_count))

        if rows_that_need_hatch_count > 0:
            counter = 0
            query = (
                "UPDATE raid "
                "SET pokemon_id = %s "
                "WHERE gym_id = %s"
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
                    logger.error(
                        'Something is wrong with the indexing on your table you raids on this id {}', row[0])
                else:
                    logger.error(
                        'The row we wanted to update did not get updated that had id {}', row[0])

            if counter == rows_that_need_hatch_count:
                logger.info(
                    "{} gym(s) were updated as part of the regular level 5 egg hatching checks", counter)
            else:
                logger.warning(
                    "There was an issue and the number expected the hatch did not match the successful updates. "
                    "Expected {} Actual {}", rows_that_need_hatch_count, counter)
        else:
            logger.info('No Eggs due for hatching')

    def db_timestring_to_unix_timestamp(self, timestring):
        try:
            dt = datetime.strptime(timestring, '%Y-%m-%d %H:%M:%S.%f')
        except ValueError:
            dt = datetime.strptime(timestring, '%Y-%m-%d %H:%M:%S')
        unixtime = (dt - datetime(1970, 1, 1)).total_seconds()
        return unixtime

    def get_next_raid_hatches(self, delay_after_hatch, geofence_helper=None):
        logger.debug("RmWrapper::get_next_raid_hatches called")
        db_time_to_check = datetime.utcfromtimestamp(
            time.time()).strftime("%Y-%m-%d %H:%M:%S")

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
                logger.warning("lat or lng is none")
                continue
            elif geofence_helper and not geofence_helper.is_coord_inside_include_geofence([latitude, longitude]):
                logger.debug("Excluded hatch at {}, {} since the coordinate is not inside the given include fences", str(
                    latitude), str(longitude))
                continue
            timestamp = self.db_timestring_to_unix_timestamp(str(start))
            data.append((timestamp + delay_after_hatch,
                         Location(latitude, longitude)))

        logger.debug("Latest Q: {}", str(data))
        return data

    def submit_raid(self, gym, pkm, lvl, start, end, type, raid_no, capture_time, unique_hash="123",
                    MonWithNoEgg=False):
        logger.debug("RmWrapper::submit_raid called")
        logger.debug("[Crop: {} ({}) ] submit_raid: Submitting raid", str(
            raid_no), str(unique_hash))

        if self.raid_exist(gym, type, raid_no, unique_hash=str(unique_hash), mon=pkm):
            self.refresh_times(gym, raid_no, capture_time)
            logger.debug("[Crop: {} ({})] submit_raid: {} already submitted, ignoring", str(
                raid_no), str(unique_hash), str(type))
            logger.debug("RmWrapper::submit_raid done")
            return False

        if start is not None:
            start_db = datetime.utcfromtimestamp(
                float(start)).strftime("%Y-%m-%d %H:%M:%S")
            start = time.mktime(
                datetime.utcfromtimestamp(float(start)).timetuple())

        if end is not None:
            end_db = datetime.utcfromtimestamp(
                float(end)).strftime("%Y-%m-%d %H:%M:%S")
            end = time.mktime(
                datetime.utcfromtimestamp(float(end)).timetuple())

        egg_hatched = False

        now_timestamp = time.mktime(
            datetime.utcfromtimestamp(float(capture_time)).timetuple())
        logger.debug(now_timestamp)

        logger.debug("[Crop: {} ({})] submit_raid: Submitting something of type {}", str(
            raid_no), str(unique_hash), str(type))
        logger.info("Submitting gym: {}, lvl: {}, start and spawn: {}, end: {}, mon: {}",
                    gym, lvl, start, end, pkm)

        # always insert timestamp to last_scanned to have rows change if raid has been reported before

        if MonWithNoEgg:
            start = int(end) - (int(self.application_args.raid_time) * 60)
            query = (
                "UPDATE raid "
                "SET level = %s, spawn = FROM_UNIXTIME(%s), start = %s, end = %s, "
                "pokemon_id = %s, last_scanned = FROM_UNIXTIME(%s), cp = %s, "
                "move_1 = %s, move_2 = %s "
                "WHERE gym_id = %s"
            )
            vals = (
                lvl, now_timestamp, start, end_db, pkm, int(
                    time.time()), '999', '1', '1', gym
            )
        elif end is None or start is None:
            # no end or start time given, just update anything there is
            logger.info(
                "Updating without end- or starttime - we should've seen the egg before")
            query = (
                "UPDATE raid "
                "SET level = %s, pokemon_id = %s, last_scanned = FROM_UNIXTIME(%s), cp = %s, "
                "move_1 = %s, move_2 = %s "
                "WHERE gym_id = %s"
            )
            vals = (
                lvl, pkm, int(time.time()), '999', '1', '1', gym
            )
            found_end_time, end_time = self.get_raid_endtime(
                gym, raid_no, unique_hash=unique_hash)
            if found_end_time:
                egg_hatched = True
        else:
            query = (
                "UPDATE raid "
                "SET level = %s, spawn = FROM_UNIXTIME(%s), start = %s, end = %s, "
                "pokemon_id = %s, last_scanned = FROM_UNIXTIME(%s), cp = %s, "
                "move_1 = %s, move_2 = %s "
                "WHERE gym_id = %s"
            )
            vals = (
                lvl, now_timestamp, start_db, end_db, pkm, int(
                    time.time()), '999', '1', '1', gym
            )

        affected_rows = self.execute(query, vals, commit=True)

        if affected_rows == 0 and not egg_hatched:
            # we need to insert the raid...
            if MonWithNoEgg:
                # submit mon without egg info -> we have an endtime
                logger.debug("Inserting mon without egg")
                start = end - (int(self.application_args.raid_time) * 60)
                query = (
                    "INSERT INTO raid (gym_id, level, spawn, start, end, pokemon_id, last_scanned, cp, "
                    "move_1, move_2) "
                    "VALUES(%s, %s, FROM_UNIXTIME(%s), %s, %s, %s, "
                    "FROM_UNIXTIME(%s), 999, 1, 1)"
                )
                vals = (
                    gym, lvl, now_timestamp, start_db, end_db, pkm, int(
                        time.time())
                )
            elif end is None and start is None:
                logger.debug("Inserting without end or start")
                # no end or start time given, just inserting won't help much...
                logger.warning("Useless to insert without endtime...")
                return False
            else:
                # we have start and end, mon is either with egg or we're submitting an egg
                start = int(end) - (int(self.application_args.raid_time) * 60)
                query = (
                    "INSERT INTO raid (gym_id, level, spawn, start, end, pokemon_id, last_scanned, cp, "
                    "move_1, move_2) "
                    "VALUES (%s, %s, FROM_UNIXTIME(%s), %s, %s, %s, "
                    "FROM_UNIXTIME(%s), 999, 1, 1)"
                )
                vals = (gym, lvl, now_timestamp, start_db,
                        end_db, pkm, int(time.time()))

            self.execute(query, vals, commit=True)

        logger.debug("[Crop: {} ({})] submit_raid: Submit finished",
                    str(raid_no), str(unique_hash))
        self.refresh_times(gym, raid_no, capture_time)

        logger.debug("RmWrapper::submit_raid done")
        return True

    def read_raid_endtime(self, gym, raid_no, unique_hash="123"):
        logger.debug("RmWrapper::read_raid_endtime called")
        logger.debug("[Crop: {} ({})] read_raid_endtime: Check DB for existing mon", str(
            raid_no), str(unique_hash))
        now = datetime.utcfromtimestamp(
            time.time()).strftime("%Y-%m-%d %H:%M:%S")

        query = (
            "SELECT raid.end "
            "FROM raid "
            "WHERE STR_TO_DATE(raid.end, '%Y-%m-%d %H:%i:%S') >= "
            "STR_TO_DATE(%s, '%Y-%m-%d %H:%i:%S') AND gym_id = %s"
        )
        vals = (
            now, gym
        )

        res = self.execute(query, vals)
        number_of_rows = len(res)

        if number_of_rows > 0:
            for row in res:
                logger.debug("[Crop: {} ({})] read_raid_endtime: Found Rows: {}", str(
                    raid_no), str(unique_hash), str(number_of_rows))
                logger.debug("[Crop: {} ({})] read_raid_endtime: Endtime already submitted", str(
                    raid_no), str(unique_hash))
                logger.debug("RmWrapper::read_raid_endtime done")
                return True

        logger.debug("[Crop: {} ({})] read_raid_endtime: Endtime is new", str(
            raid_no), str(unique_hash))
        logger.debug("RmWrapper::read_raid_endtime done")
        return False

    def get_raid_endtime(self, gym, raid_no, unique_hash="123"):
        logger.debug("RmWrapper::get_raid_endtime called")
        logger.debug("[Crop: {} ({})] get_raid_endtime: Check DB for existing mon", str(
            raid_no), str(unique_hash))

        now = datetime.utcfromtimestamp(
            time.time()).strftime('%Y-%m-%d %H:%M:%S')
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
                logger.debug("[Crop: {} ({})] get_raid_endtime: Returning found endtime", str(
                    raid_no), str(unique_hash))
                logger.debug("[Crop: {} ({})] get_raid_endtime: Time: {}", str(
                    raid_no), str(unique_hash), str(row[0]))

                return True, row[0]

        logger.debug("[Crop: {} ({}) ] get_raid_endtime: No matching endtime found", str(
            raid_no), str(unique_hash))
        return False, None

    def raid_exist(self, gym, type, raid_no, unique_hash="123", mon=0):
        logger.debug("RmWrapper::raid_exist called")
        logger.debug("[Crop: {} ({})] raid_exist: Check DB for existing entry", str(
            raid_no), str(unique_hash))
        now = datetime.utcfromtimestamp(
            time.time()).strftime('%Y-%m-%d %H:%M:%S')

        # TODO: consider reducing the code...

        if type == "EGG":
            logger.debug("[Crop: {} ({})] raid_exist: Check for egg", str(
                raid_no), str(unique_hash))
            query = (
                "SELECT start "
                "FROM raid "
                "WHERE STR_TO_DATE(raid.start, '%Y-%m-%d %H:%i:%S') >= "
                "STR_TO_DATE(%s, '%Y-%m-%d %H:%i:%S') and gym_id = %s"
            )
            vals = (
                now, gym
            )

            res = self.execute(query, vals)
            number_of_rows = len(res)
            if number_of_rows > 0:
                logger.debug("[Crop: {} ({})] raid_exist: Found Rows: {}", str(
                    raid_no), str(unique_hash), str(number_of_rows))
                logger.debug("[Crop: {} ({})] raid_exist: Egg already submitted", str(
                    raid_no), str(unique_hash))
                logger.debug("RmWrapper::raid_exist done")
                return True
            else:
                logger.debug("[Crop: {} ({})] raid_exist: Egg is new",
                            str(raid_no), str(unique_hash))
                logger.debug("RmWrapper::raid_exist done")
                return False
        else:
            logger.debug("[Crop: {} ({})] raid_exist: Check for MON", str(
                raid_no), str(unique_hash))
            query = (
                "SELECT start "
                "FROM raid "
                "WHERE STR_TO_DATE(raid.start, '%Y-%m-%d %H:%i:%S') <= "
                "STR_TO_DATE(%s, '%Y-%m-%d %H:%i:%S') AND "
                "STR_TO_DATE(raid.end, '%Y-%m-%d %H:%i:%S') >= "
                "STR_TO_DATE(%s, '%Y-%m-%d %H:%i:%S') "
                "AND gym_id = %s AND pokemon_id = %s"
            )
            vals = (
                now, now, gym, mon
            )

            res = self.execute(query, vals)
            number_of_rows = len(res)
            if number_of_rows > 0:
                logger.debug("[Crop: {} ({})] raid_exist: Found Rows: {}", str(
                    raid_no), str(unique_hash), str(number_of_rows))
                logger.debug("[Crop: {} ({})] raid_exist: Mon already submitted", str(
                    raid_no), str(unique_hash))
                logger.debug("RmWrapper::raid_exist done")
                return True
            else:
                logger.debug("[Crop: {} ({})] raid_exist: Mon is new",
                            str(raid_no), str(unique_hash))
                logger.debug("RmWrapper::raid_exist done")
                return False

    def refresh_times(self, gym, raid_no, capture_time, unique_hash="123"):
        logger.debug("RmWrapper::refresh_times called")
        logger.debug("[Crop: {} ({})] raid_exist: Check for Egg",
                     str(raid_no), str(unique_hash))
        now = datetime.utcfromtimestamp(
            float(capture_time)).strftime("%Y-%m-%d %H:%M:%S")

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
            "SET last_scanned = %s "
            "WHERE gym_id = %s"
        )
        vals = (
            now, gym
        )
        self.execute(query, vals, commit=True)

    def get_near_gyms(self, lat, lng, hash, raid_no, dist, unique_hash="123"):
        logger.debug("RmWrapper::get_near_gyms called")

        query = (
            "SELECT gym.gym_id, "
            "( 6371 * "
            "acos( cos(radians(%s)) "
            "* cos(radians(latitude)) "
            "* cos(radians(longitude) - radians(%s)) "
            "+ sin(radians(%s)) "
            "* sin(radians(latitude))"
            ")"
            ") "
            "AS distance, gym.latitude, gym.longitude, gymdetails.name, gymdetails.description, gymdetails.url "
            "FROM gym "
            "LEFT JOIN gymdetails ON gym.gym_id = gymdetails.gym_id "
            "HAVING distance <= %s OR distance IS NULL "
            "ORDER BY distance"
        )

        vals = (
            float(lat), float(lng), float(lat), float(dist)
        )
        data = []
        res = self.execute(query, vals)
        for (gym_id, distance, latitude, longitude, name, description, url) in res:
            data.append([gym_id, distance, latitude,
                         longitude, name, description, url])
        logger.debug("RmWrapper::get_near_gyms done")
        return data

    def set_scanned_location(self, lat, lng, capture_time):
        logger.debug("RmWrapper::set_scanned_location called")
        now = datetime.utcfromtimestamp(
            time.time()).strftime('%Y-%m-%d %H:%M:%S')
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

        logger.debug(
            "RmWrapper::set_scanned_location Done setting location...")
        return True

    def download_gym_images(self):
        logger.debug("RmWrapper::download_gym_images called")
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
                filename = url_image_path + '_' + str(gym_id) + '_.jpg'
                logger.debug('Downloading', filename)
                self.__download_img(str(url), str(filename))

        logger.debug('Finished downloading gym images...')

        return True

    def get_gym_infos(self, id=False):
        logger.debug("RmWrapper::get_gym_infos called")
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
            gyminfo[gym_id] = self.__encode_hash_json(team_id, float(latitude), float(longitude), str(name).replace('"', '\\"').replace('\n', '\\n'),
                                                      description, url)
        return gyminfo

    def gyms_from_db(self, geofence_helper):
        logger.debug("RmWrapper::gyms_from_db called")
        if geofence_helper is None:
            logger.error("No geofence_helper! Not fetching gyms.")
            return []

        logger.debug("Filtering with rectangle")
        rectangle = geofence_helper.get_polygon_from_fence()

        query = (
            "SELECT latitude, longitude "
            "FROM gym "
            "WHERE "
            "latitude >= %s AND longitude >= %s AND "
            "latitude <= %s AND longitude <= %s"
        )
        res = self.execute(query, rectangle)
        list_of_coords: List[Location] = []
        for (latitude, longitude) in res:
            list_of_coords.append(Location(latitude, longitude))
        logger.debug("Got {} coordinates in this rect (minLat, minLon, "
                     "maxLat, maxLon): {}", len(list_of_coords), str(rectangle))

        geofenced_coords = geofence_helper.get_geofenced_coordinates(
            list_of_coords)
        return geofenced_coords

    def update_encounters_from_db(self, geofence_helper, latest=0):
        logger.debug("RmWrapper::update_encounters_from_db called")
        if geofence_helper is None:
            logger.error("No geofence_helper! Not fetching encounters.")
            return 0, {}

        logger.debug("Filtering with rectangle")
        rectangle = geofence_helper.get_polygon_from_fence()
        query = (
            "SELECT latitude, longitude, encounter_id, "
            "UNIX_TIMESTAMP(CONVERT_TZ(disappear_time + INTERVAL 1 HOUR, '+00:00', @@global.time_zone)), "
            "UNIX_TIMESTAMP(CONVERT_TZ(last_modified, '+00:00', @@global.time_zone)) "
            "FROM pokemon "
            "WHERE "
            "latitude >= %s AND longitude >= %s AND "
            "latitude <= %s AND longitude <= %s AND "
            "cp IS NOT NULL AND "
            "disappear_time > UTC_TIMESTAMP() - INTERVAL 1 HOUR AND "
            "UNIX_TIMESTAMP(last_modified) > %s "
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
        logger.debug("Got {} encounter coordinates within this rect and age (minLat, minLon, maxLat, maxLon, last_modified): {}", len(
            encounter_id_coords), str(params))
        encounter_id_infos = {}
        for (latitude, longitude, encounter_id, disappear_time, last_modified) in encounter_id_coords:
            encounter_id_infos[encounter_id] = disappear_time

        return latest, encounter_id_infos

    def stops_from_db(self, geofence_helper):
        logger.debug("RmWrapper::stops_from_db called")

        minLat, minLon, maxLat, maxLon = geofence_helper.get_polygon_from_fence()

        query = (
            "SELECT latitude, longitude "
            "FROM pokestop "
            "WHERE (latitude >= {} AND longitude >= {} "
            "AND latitude <= {} AND longitude <= {}) "
        ).format(minLat, minLon, maxLat, maxLon)

        res = self.execute(query)
        list_of_coords: List[Location] = []
        for (latitude, longitude) in res:
            list_of_coords.append(Location(latitude, longitude))

        if geofence_helper is not None:
            geofenced_coords = geofence_helper.get_geofenced_coordinates(
                list_of_coords)
            return geofenced_coords
        else:
            return list_of_coords

    def update_insert_weather(self, cell_id, gameplay_weather, capture_time, cloud_level=0, rain_level=0, wind_level=0,
                              snow_level=0, fog_level=0, wind_direction=0, weather_daytime=0):
        logger.debug("RmWrapper::update_insert_weather called")
        now = datetime.utcfromtimestamp(
            time.time()).strftime('%Y-%m-%d %H:%M:%S')

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
                wind_direction, gameplay_weather, None, None, weather_daytime, str(
                    now),
                fog_level, cloud_level, snow_level, wind_direction, weather_daytime, real_lat, real_lng,
                gameplay_weather, str(now))

        self.execute(query, data, commit=True)

        return True

    def submit_mon_iv(self, origin: str, timestamp: float, encounter_proto: dict, mitm_mapper):
        wild_pokemon = encounter_proto.get("wild_pokemon", None)
        if wild_pokemon is None:
            return

        logger.debug("Updating IV sent by {} for encounter at {}".format(str(origin), str(timestamp)))

        now = datetime.utcfromtimestamp(
            time.time()).strftime('%Y-%m-%d %H:%M:%S')

        spawnid = int(str(wild_pokemon['spawnpoint_id']), 16)

        getdetspawntime = self.get_detected_endtime(str(spawnid))
        despawn_time_unix = gen_despawn_timestamp(getdetspawntime)
        despawn_time = datetime.utcfromtimestamp(
            despawn_time_unix).strftime('%Y-%m-%d %H:%M:%S')

        latitude = wild_pokemon.get("latitude")
        longitude = wild_pokemon.get("longitude")
        pokemon_data = wild_pokemon.get("pokemon_data")
        encounter_id = wild_pokemon['encounter_id']
        shiny = wild_pokemon['pokemon_data']['display'].get('is_shiny', 0)

        if encounter_id < 0:
            encounter_id = encounter_id + 2**64

        mitm_mapper.collect_mon_iv_stats(origin, encounter_id, int(shiny))

        if getdetspawntime is None:
            logger.debug("{}: updating IV mon #{} at {}, {}. Despawning at {} (init)",
                         str(origin), pokemon_data["id"], latitude, longitude, despawn_time)
        else:
            logger.debug("{}: updating IV mon #{} at {}, {}. Despawning at {} (non-init)",
                         str(origin), pokemon_data["id"], latitude, longitude, despawn_time)

        capture_probability = encounter_proto.get("capture_probability")
        capture_probability_list = capture_probability.get("capture_probability_list")
        if capture_probability_list is not None:
            capture_probability_list = capture_probability_list.replace(
                "[", "").replace("]", "").split(",")

        pokemon_display = pokemon_data.get("display")
        if pokemon_display is None:
            pokemon_display = {}
            # initialize to not run into nullpointer

        query = (
            "INSERT INTO pokemon (encounter_id, spawnpoint_id, pokemon_id, latitude, longitude, disappear_time, "
            "individual_attack, individual_defense, individual_stamina, move_1, move_2, cp, cp_multiplier, "
            "weight, height, gender, catch_prob_1, catch_prob_2, catch_prob_3, rating_attack, rating_defense, "
            "weather_boosted_condition, last_modified, costume, form) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, "
            "%s, %s, %s, %s, %s) "
            "ON DUPLICATE KEY UPDATE last_modified=VALUES(last_modified), disappear_time=VALUES(disappear_time), "
            "individual_attack=VALUES(individual_attack), individual_defense=VALUES(individual_defense), "
            "individual_stamina=VALUES(individual_stamina), move_1=VALUES(move_1), move_2=VALUES(move_2), "
            "cp=VALUES(cp), cp_multiplier=VALUES(cp_multiplier), weight=VALUES(weight), height=VALUES(height), "
            "gender=VALUES(gender), catch_prob_1=VALUES(catch_prob_1), catch_prob_2=VALUES(catch_prob_2), "
            "catch_prob_3=VALUES(catch_prob_3), rating_attack=VALUES(rating_attack), "
            "rating_defense=VALUES(rating_defense), weather_boosted_condition=VALUES(weather_boosted_condition), "
            "costume=VALUES(costume), form=VALUES(form), pokemon_id=VALUES(pokemon_id)"
        )

        vals = (
            encounter_id,
            spawnid,
            pokemon_data.get('id'),
            latitude, longitude, despawn_time,
            pokemon_data.get("individual_attack"),
            pokemon_data.get("individual_defense"),
            pokemon_data.get("individual_stamina"),
            pokemon_data.get("move_1"),
            pokemon_data.get("move_2"),
            pokemon_data.get("cp"),
            pokemon_data.get("cp_multiplier"),
            pokemon_data.get("weight"),
            pokemon_data.get("height"),
            pokemon_display.get("gender_value", None),
            float(capture_probability_list[0]),
            float(capture_probability_list[1]),
            float(capture_probability_list[2]),
            None, None,
            pokemon_display.get('weather_boosted_value', None),
            now,
            pokemon_display.get("costume_value", None),
            pokemon_display.get("form_value", None)
        )

        self.execute(query, vals, commit=True)
        logger.debug("Done updating mon in DB")

        return True

    def submit_mons_map_proto(self, origin: str, map_proto: dict, mon_ids_iv: Optional[List[int]], mitm_mapper):
        logger.debug(
            "RmWrapper::submit_mons_map_proto called with data received from {}", str(origin))
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
                encounter_id = wild_mon['encounter_id']

                if encounter_id < 0:
                    encounter_id = encounter_id + 2**64

                mitm_mapper.collect_mon_stats(origin, str(encounter_id))

                now = datetime.utcfromtimestamp(
                    time.time()).strftime('%Y-%m-%d %H:%M:%S')

                # get known spawn end time and feed into despawn time calculation
                getdetspawntime = self.get_detected_endtime(str(spawnid))
                despawn_time_unix = gen_despawn_timestamp(getdetspawntime)
                despawn_time = datetime.utcfromtimestamp(
                    despawn_time_unix).strftime('%Y-%m-%d %H:%M:%S')

                if getdetspawntime is None:
                    logger.debug("{}: adding mon (#{}) at {}, {}. Despawns at {} (init) ({})", str(
                        origin), mon_id, lat, lon, despawn_time, spawnid)
                else:
                    logger.debug("{}: adding mon (#{}) at {}, {}. Despawns at {} (non-init) ({})",
                                 str(origin), mon_id, lat, lon, despawn_time, spawnid)

                mon_args.append(
                    (
                        encounter_id, spawnid, mon_id, lat, lon,
                        despawn_time,
                        # TODO: consider .get("XXX", None)
                        None, None, None, None, None, None, None, None, None,
                        wild_mon['pokemon_data']['display']['gender_value'],
                        None, None, None, None, None,
                        wild_mon['pokemon_data']['display']['weather_boosted_value'],
                        now, wild_mon['pokemon_data']['display']['costume_value'],
                        wild_mon['pokemon_data']['display']['form_value']
                    )
                )

        self.executemany(query_mons, mon_args, commit=True)
        return True

    def submit_pokestops_map_proto(self, origin, map_proto):
        logger.debug(
            "RmWrapper::submit_pokestops_map_proto called with data received from {}", str(origin))
        cells = map_proto.get("cells", None)
        if cells is None:
            return False
        pokestop_args = []

        query_pokestops = (
            "INSERT INTO pokestop (pokestop_id, enabled, latitude, longitude, last_modified, lure_expiration, "
            "last_updated, active_fort_modifier, incident_start, incident_expiration) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) "
            "ON DUPLICATE KEY UPDATE last_updated=VALUES(last_updated), lure_expiration=VALUES(lure_expiration), "
            "last_modified=VALUES(last_modified), latitude=VALUES(latitude), longitude=VALUES(longitude), "
            "active_fort_modifier=VALUES(active_fort_modifier), incident_start=VALUES(incident_start), "
            "incident_expiration=VALUES(incident_expiration)"
        )

        for cell in cells:
            for fort in cell['forts']:
                if fort['type'] == 1:
                    pokestop_args.append(
                        self.__extract_args_single_pokestop(fort))

        self.executemany(query_pokestops, pokestop_args, commit=True)
        return True

    def submit_gyms_map_proto(self, origin, map_proto):
        logger.debug(
            "RmWrapper::submit_gyms_map_proto called with data received from {}", str(origin))
        cells = map_proto.get("cells", None)
        if cells is None:
            return False
        gym_args = []
        gym_details_args = []
        now = datetime.utcfromtimestamp(
            time.time()).strftime("%Y-%m-%d %H:%M:%S")

        query_gym = (
            "INSERT INTO gym (gym_id, team_id, guard_pokemon_id, slots_available, enabled, latitude, longitude, "
            "total_cp, is_in_battle, last_modified, last_scanned, is_ex_raid_eligible) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) "
            "ON DUPLICATE KEY UPDATE "
            "guard_pokemon_id=VALUES(guard_pokemon_id), team_id=VALUES(team_id), "
            "slots_available=VALUES(slots_available), last_scanned=VALUES(last_scanned), "
            "last_modified=VALUES(last_modified), latitude=VALUES(latitude), longitude=VALUES(longitude), "
            "is_ex_raid_eligible=VALUES(is_ex_raid_eligible)"
        )
        query_gym_details = (
            "INSERT INTO gymdetails (gym_id, name, url, last_scanned) "
            "VALUES (%s, %s, %s, %s) "
            "ON DUPLICATE KEY UPDATE last_scanned=VALUES(last_scanned), "
            "url=IF(VALUES(url) IS NOT NULL AND VALUES(url) <> '', VALUES(url), url)"
        )

        for cell in cells:
            for gym in cell['forts']:
                if gym['type'] == 0:
                    guard_pokemon_id = gym['gym_details']['guard_pokemon']
                    gymid = gym['id']
                    team_id = gym['gym_details']['owned_by_team']
                    latitude = gym['latitude']
                    longitude = gym['longitude']
                    slots_available = gym['gym_details']['slots_available']
                    last_modified_ts = gym['last_modified_timestamp_ms'] / 1000
                    last_modified = datetime.utcfromtimestamp(
                        last_modified_ts).strftime("%Y-%m-%d %H:%M:%S")
                    is_ex_raid_eligible = gym['gym_details']['is_ex_raid_eligible']

                    gym_args.append(
                        (
                            gymid, team_id, guard_pokemon_id, slots_available,
                            1,  # enabled
                            latitude, longitude,
                            0,  # total CP
                            0,  # is_in_battle
                            last_modified,  # last_modified
                            now,   # last_scanned
                            is_ex_raid_eligible
                        )
                    )

                    gym_details_args.append(
                        (
                            gym['id'], "unknown", gym['image_url'], now
                        )
                    )
        self.executemany(query_gym, gym_args, commit=True)
        self.executemany(query_gym_details, gym_details_args, commit=True)
        logger.debug("{}: submit_gyms done", str(origin))
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
        description = map_proto["description"]
        url = map_proto["url"]

        set_keys = []
        vals = []

        if name is not None and name != "":
            set_keys.append("name=%s")
            vals.append(name)
        if description is not None and description != "":
            set_keys.append("description=%s")
            vals.append(description)
        if url is not None and url != "":
            set_keys.append("url=%s")
            vals.append(url)

        if len(set_keys) == 0:
            return False

        query = "UPDATE gymdetails SET " + ",".join(set_keys) + " WHERE gym_id = %s"
        vals.append(gym_id)

        self.execute((query), tuple(vals), commit=True)

        return True

    def submit_raids_map_proto(self, origin: str, map_proto: dict, mitm_mapper):
        logger.debug(
            "RmWrapper::submit_raids_map_proto called with data received from {}", str(origin))
        cells = map_proto.get("cells", None)
        if cells is None:
            return False
        raid_args = []
        now = datetime.utcfromtimestamp(
            time.time()).strftime("%Y-%m-%d %H:%M:%S")

        query_raid = (
            "INSERT INTO raid (gym_id, level, spawn, start, end, pokemon_id, cp, move_1, move_2, last_scanned, form, is_exclusive, gender) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) "
            "ON DUPLICATE KEY UPDATE level=VALUES(level), spawn=VALUES(spawn), start=VALUES(start), "
            "end=VALUES(end), pokemon_id=VALUES(pokemon_id), cp=VALUES(cp), move_1=VALUES(move_1), "
            "move_2=VALUES(move_2), last_scanned=VALUES(last_scanned), is_exclusive=VALUES(is_exclusive), "
            "form=VALUES(form), gender=VALUES(gender)"
        )

        for cell in cells:
            for gym in cell['forts']:
                if gym['type'] == 0 and gym['gym_details']['has_raid']:
                    gym_has_raid = gym['gym_details']['raid_info']['has_pokemon']
                    if gym_has_raid:
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

                    raidend_date = datetime.utcfromtimestamp(
                        float(raidendSec)).strftime("%Y-%m-%d %H:%M:%S")
                    raidspawn_date = datetime.utcfromtimestamp(float(raidspawnSec)).strftime(
                        "%Y-%m-%d %H:%M:%S")
                    raidstart_date = datetime.utcfromtimestamp(float(raidbattleSec)).strftime(
                        "%Y-%m-%d %H:%M:%S")

                    is_exclusive = gym['gym_details']['raid_info']['is_exclusive']
                    level = gym['gym_details']['raid_info']['level']
                    gymid = gym['id']

                    mitm_mapper.collect_raid_stats(origin, gymid)

                    logger.debug("Adding/Updating gym {} with level {} ending at {}",
                                 str(gymid), str(level), str(raidend_date))

                    raid_args.append(
                        (
                            gymid,
                            level,
                            raidspawn_date,
                            raidstart_date,
                            raidend_date,
                            pokemon_id, cp, move_1, move_2, now,
                            form,
                            is_exclusive,
                            gender
                        )
                    )
        self.executemany(query_raid, raid_args, commit=True)
        logger.debug(
            "RmWrapper::submit_raids_map_proto: Done submitting raids with data received from {}", str(origin))
        return True

    def submit_weather_map_proto(self, origin, map_proto, received_timestamp):
        logger.debug(
            "RmWrapper::submit_weather_map_proto called with data received from {}", str(origin))
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
                self.__extract_args_single_weather(
                    client_weather, time_of_day, received_timestamp)
            )
        self.executemany(query_weather, list_of_weather_args, commit=True)
        return True

    def get_to_be_encountered(self, geofence_helper, min_time_left_seconds, eligible_mon_ids: Optional[List[int]]):
        if min_time_left_seconds is None or eligible_mon_ids is None:
            logger.warning("RmWrapper::get_to_be_encountered: Not returning any encounters since no time left or "
                           "eligible mon IDs specified")
            return []
        logger.debug("Getting mons to be encountered")
        query = (
            "SELECT latitude, longitude, encounter_id, spawnpoint_id, pokemon_id, "
            "TIMESTAMPDIFF(SECOND, UTC_TIMESTAMP(), disappear_time) AS expire "
            "FROM pokemon "
            "WHERE individual_attack IS NULL AND individual_defense IS NULL AND individual_stamina IS NULL "
            "AND encounter_id != 0 "
            "and (disappear_time BETWEEN DATE_ADD(UTC_TIMESTAMP(), INTERVAL %s SECOND) "
            "and DATE_ADD(UTC_TIMESTAMP(), INTERVAL 60 MINUTE))"
            "ORDER BY expire ASC"
        )

        vals = (
            int(min_time_left_seconds),
        )

        results = self.execute(query, vals, commit=False)

        next_to_encounter = []
        for latitude, longitude, encounter_id, spawnpoint_id, pokemon_id, expire in results:
            if pokemon_id not in eligible_mon_ids:
                continue
            elif latitude is None or longitude is None:
                logger.warning("lat or lng is none")
                continue
            elif geofence_helper and not geofence_helper.is_coord_inside_include_geofence([latitude, longitude]):
                logger.debug("Excluded encounter at {}, {} since the coordinate is not inside the given include fences", str(
                    latitude), str(longitude))
                continue

            next_to_encounter.append((pokemon_id, Location(latitude, longitude), encounter_id))

        # now filter by the order of eligible_mon_ids
        to_be_encountered = []
        i = 0
        for mon_prio in eligible_mon_ids:
            for mon in next_to_encounter:
                if mon_prio == mon[0]:
                    to_be_encountered.append((i, mon[1], mon[2]))
            i += 1
        return to_be_encountered

    def __encode_hash_json(self, team_id, latitude, longitude, name, description, url):
        return (
            {'team_id': team_id, 'latitude': latitude, 'longitude': longitude, 'name': name, 'description': '',
             'url': url})

    def __download_img(self, url, file_name):
        retry = 1
        if not url:
            return
        while retry <= 5:
            try:
                r = requests.get(url, stream=True, timeout=10)
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
                    logger.info('retry: {}', retry)
                else:
                    logger.info('Failed to download after 5 retry')

    def __extract_args_single_pokestop(self, stop_data):
        if stop_data['type'] != 1:
            logger.warning("{} is not a pokestop", str(stop_data))
            return None

        now = datetime.utcfromtimestamp(
            time.time()).strftime("%Y-%m-%d %H:%M:%S")
        last_modified = datetime.utcfromtimestamp(
            stop_data['last_modified_timestamp_ms'] / 1000).strftime("%Y-%m-%d %H:%M:%S")
        lure = '1970-01-01 00:00:00'
        active_fort_modifier = None
        incident_start = None
        incident_expiration = None

        if len(stop_data['active_fort_modifier']) > 0:
            active_fort_modifier = stop_data['active_fort_modifier'][0]
            lure = datetime.utcfromtimestamp(30 * 60 + (stop_data['last_modified_timestamp_ms'] / 1000)).strftime("%Y-%m-%d %H:%M:%S")

        if "pokestop_display" in stop_data:
            start_ms = stop_data["pokestop_display"]["incident_start_ms"]
            expiration_ms = stop_data["pokestop_display"]["incident_expiration_ms"]

            if start_ms > 0:
                incident_start = datetime.utcfromtimestamp(start_ms / 1000).strftime("%Y-%m-%d %H:%M:%S")

            if expiration_ms > 0:
                incident_expiration = datetime.utcfromtimestamp(expiration_ms / 1000).strftime("%Y-%m-%d %H:%M:%S")

        return stop_data['id'], 1, stop_data['latitude'], stop_data['longitude'], last_modified, lure, now, active_fort_modifier, incident_start, incident_expiration

    def __extract_args_single_weather(self, client_weather_data, time_of_day, received_timestamp):
        now = datetime.utcfromtimestamp(
            time.time()).strftime('%Y-%m-%d %H:%M:%S')
        cell_id = client_weather_data["cell_id"]
        real_lat, real_lng = S2Helper.middle_of_cell(cell_id)

        display_weather_data = client_weather_data.get("display_weather", None)
        if display_weather_data is None:
            return None
        else:
            gameplay_weather = client_weather_data["gameplay_weather"]["gameplay_condition"]

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

    def check_stop_quest(self, latitude, longitude):
        logger.debug("RmWrapper::check_stop_quest called")
        query = (
            "SELECT trs_quest.GUID "
            "from trs_quest inner join pokestop on pokestop.pokestop_id = trs_quest.GUID where "
            "from_unixtime(trs_quest.quest_timestamp,'%Y-%m-%d') = "
            "date_format(DATE_ADD( now() , INTERVAL '-15' MINUTE ), '%Y-%m-%d') "
            "and pokestop.latitude=%s and pokestop.longitude=%s"
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
        logger.debug("RmWrapper::stop_from_db_without_quests called")

        minLat, minLon, maxLat, maxLon = geofence_helper.get_polygon_from_fence()

        query = (
            "SELECT pokestop.latitude, pokestop.longitude "
            "FROM pokestop "
            "LEFT JOIN trs_quest ON pokestop.pokestop_id = trs_quest.GUID "
            "WHERE (pokestop.latitude >= {} AND pokestop.longitude >= {} "
            "AND pokestop.latitude <= {} AND pokestop.longitude <= {}) "
        ).format(minLat, minLon, maxLat, maxLon)

        if not levelmode:
            query_addon = ("AND DATE(from_unixtime(trs_quest.quest_timestamp,'%Y-%m-%d')) <> CURDATE() "
                           "OR trs_quest.GUID IS NULL")

            query = query + query_addon

        res = self.execute(query)
        list_of_coords: List[Location] = []
        for (latitude, longitude) in res:
            list_of_coords.append(Location(latitude, longitude))

        if geofence_helper is not None:
            geofenced_coords = geofence_helper.get_geofenced_coordinates(
                list_of_coords)
            return geofenced_coords
        else:
            return list_of_coords

    def quests_from_db(self, neLat=None, neLon=None, swLat=None, swLon=None, oNeLat=None, oNeLon=None,
                       oSwLat=None, oSwLon=None, timestamp=None):
        logger.debug("RmWrapper::quests_from_db called")
        questinfo = {}

        query = (
            "SELECT pokestop.pokestop_id, pokestop.latitude, pokestop.longitude, trs_quest.quest_type, "
            "trs_quest.quest_stardust, trs_quest.quest_pokemon_id, trs_quest.quest_reward_type, "
            "trs_quest.quest_item_id, trs_quest.quest_item_amount, pokestop.name, pokestop.image, "
            "trs_quest.quest_target, trs_quest.quest_condition, trs_quest.quest_timestamp, "
            "trs_quest.quest_task, trs_quest.quest_reward, trs_quest.quest_template "
            "FROM pokestop INNER JOIN trs_quest ON pokestop.pokestop_id = trs_quest.GUID "
            "WHERE DATE(from_unixtime(trs_quest.quest_timestamp,'%Y-%m-%d')) = CURDATE() "
        )

        query_where = ""

        if neLat is not None and neLon is not None and swLat is not None and swLon is not None:
            oquery_where = (
                " AND (latitude >= {} AND longitude >= {} "
                " AND latitude <= {} AND longitude <= {}) "
            ).format(swLat, swLon, neLat, neLon)

            query_where = query_where + oquery_where

        if oNeLat is not None and oNeLon is not None and oSwLat is not None and oSwLon is not None:
            oquery_where = (
                " AND NOT (latitude >= {} AND longitude >= {} "
                " AND latitude <= {} AND longitude <= {}) "
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

    def get_stops_changed_since(self, timestamp):
        query = (
            "SELECT pokestop_id, latitude, longitude, lure_expiration, name, image, active_fort_modifier, "
            "last_modified, last_updated, incident_start, incident_expiration "
            "FROM pokestop "
            "WHERE last_updated >= %s AND (DATEDIFF(lure_expiration, '1970-01-01 00:00:00') > 0 OR "
            "incident_start IS NOT NULL)"
        )

        tsdt = datetime.utcfromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")
        res = self.execute(query, (tsdt, ))

        ret = []
        for (pokestop_id, latitude, longitude, lure_expiration, name, image, active_fort_modifier,
                last_modified, last_updated, incident_start, incident_expiration) in res:

            ret.append({
                'pokestop_id': pokestop_id,
                'latitude': latitude,
                'longitude': longitude,
                'lure_expiration': int(lure_expiration.replace(tzinfo=timezone.utc).timestamp()) if lure_expiration is not None else None,
                'name': name,
                'image': image,
                'active_fort_modifier': active_fort_modifier,
                "last_modified": int(last_modified.replace(tzinfo=timezone.utc).timestamp()) if last_modified is not None else None,
                "last_updated": int(last_updated.replace(tzinfo=timezone.utc).timestamp()) if last_updated is not None else None,
                "incident_start": int(incident_start.replace(tzinfo=timezone.utc).timestamp()) if incident_start is not None else None,
                "incident_expiration": int(incident_expiration.replace(tzinfo=timezone.utc).timestamp()) if incident_expiration is not None else None
            })

        return ret

    def submit_pokestops_details_map_proto(self, map_proto):
        logger.debug("RmWrapper::submit_pokestops_details_map_proto called")
        pokestop_args = []

        query_pokestops = (
            "INSERT INTO pokestop (pokestop_id, enabled, latitude, longitude, last_modified, "
            "last_updated, name, image) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s) "
            "ON DUPLICATE KEY UPDATE last_updated=VALUES(last_updated), lure_expiration=VALUES(lure_expiration), "
            "latitude=VALUES(latitude), longitude=VALUES(longitude), name=VALUES(name), image=VALUES(image)"
        )

        pokestop_args = self.__extract_args_single_pokestop_details(map_proto)

        if pokestop_args is not None:
            self.execute(query_pokestops, pokestop_args, commit=True)
        return True

    def get_raids_changed_since(self, timestamp):
        query = (
            "SELECT raid.gym_id, raid.level, raid.spawn, raid.start, raid.end, raid.pokemon_id, "
            "raid.cp, raid.move_1, raid.move_2, raid.last_scanned, raid.form, raid.is_exclusive, raid.gender, "
            "gymdetails.name, gymdetails.url, gym.latitude, gym.longitude, "
            "gym.team_id, weather_boosted_condition, gym.is_ex_raid_eligible "
            "FROM raid "
            "LEFT JOIN gymdetails ON gymdetails.gym_id = raid.gym_id "
            "LEFT JOIN gym ON gym.gym_id = raid.gym_id "
            "WHERE raid.last_scanned >= %s"
        )

        tsdt = datetime.utcfromtimestamp(
            timestamp).strftime("%Y-%m-%d %H:%M:%S")
        res = self.execute(query, (tsdt, ))
        ret = []

        for (gym_id, level, spawn, start, end, pokemon_id,
                cp, move_1, move_2, last_scanned, form, is_exclusive, gender,
                name, url, latitude, longitude, team_id,
                weather_boosted_condition, is_ex_raid_eligible) in res:
            ret.append({
                "gym_id": gym_id,
                "level": level,
                "spawn": int(spawn.replace(tzinfo=timezone.utc).timestamp()),
                "start": int(start.replace(tzinfo=timezone.utc).timestamp()),
                "end": int(end.replace(tzinfo=timezone.utc).timestamp()),
                "pokemon_id": pokemon_id,
                "cp": cp,
                "move_1": move_1,
                "move_2": move_2,
                "last_scanned": int(last_scanned.replace(tzinfo=timezone.utc).timestamp()),
                "form": form,
                "name": name,
                "url": url,
                "latitude": latitude,
                "longitude": longitude,
                "team_id": team_id,
                "weather_boosted_condition": weather_boosted_condition,
                "is_exclusive": is_exclusive,
                "gender": gender,
                "is_ex_raid_eligible": is_ex_raid_eligible
            })

        return ret

    def get_mon_changed_since(self, timestamp):
        query = (
            "SELECT encounter_id, spawnpoint_id, pokemon_id, pokemon.latitude, pokemon.longitude, "
            "disappear_time, individual_attack, individual_defense, individual_stamina, "
            "move_1, move_2, cp, cp_multiplier, weight, height, gender, form, costume, "
            "weather_boosted_condition, last_modified, "
            "(trs_spawn.calc_endminsec IS NOT NULL) AS verified "
            "FROM pokemon "
            "LEFT JOIN trs_spawn ON pokemon.spawnpoint_id = trs_spawn.spawnpoint "
            "WHERE last_modified >= %s"
        )

        tsdt = datetime.utcfromtimestamp(
            timestamp).strftime("%Y-%m-%d %H:%M:%S")
        res = self.execute(query, (tsdt, ))
        ret = []

        for (encounter_id, spawnpoint_id, pokemon_id, latitude,
                longitude, disappear_time, individual_attack,
                individual_defense, individual_stamina, move_1, move_2,
                cp, cp_multiplier, weight, height, gender, form, costume,
                weather_boosted_condition, last_modified, verified) in res:
            ret.append({
                "encounter_id": encounter_id,
                "pokemon_id": pokemon_id,
                "last_modified": last_modified,
                "spawnpoint_id": spawnpoint_id,
                "latitude": latitude,
                "longitude": longitude,
                "disappear_time": int(disappear_time.replace(tzinfo=timezone.utc).timestamp()),
                "individual_attack": individual_attack,
                "individual_defense": individual_defense,
                "individual_stamina": individual_stamina,
                "move_1": move_1,
                "move_2": move_2,
                "cp": cp,
                "cp_multiplier": cp_multiplier,
                "gender": gender,
                "form": form,
                "costume": costume,
                "height": height,
                "weight": weight,
                "weather_boosted_condition": weather_boosted_condition,
                "spawn_verified": verified == 1
            })

        return ret

    def get_quests_changed_since(self, timestamp):
        pass

    def get_weather_changed_since(self, timestamp):
        query = (
            "SELECT * "
            "FROM weather "
            "WHERE last_updated >= %s"
        )

        tsdt = datetime.utcfromtimestamp(
            timestamp).strftime("%Y-%m-%d %H:%M:%S")
        res = self.execute(query, (tsdt, ))
        ret = []

        for (s2_cell_id, latitude, longitude, cloud_level, rain_level, wind_level,
                snow_level, fog_level, wind_direction, gameplay_weather, severity,
                warn_weather, world_time, last_updated) in res:
            ret.append({
                "s2_cell_id": s2_cell_id,
                "latitude": latitude,
                "longitude": longitude,
                "cloud_level": cloud_level,
                "rain_level": rain_level,
                "wind_level": wind_level,
                "snow_level": snow_level,
                "fog_level": fog_level,
                "wind_direction": wind_direction,
                "gameplay_weather": gameplay_weather,
                "severity": severity,
                "warn_weather": warn_weather,
                "world_time": world_time,
                "last_updated": int(last_updated.replace(tzinfo=timezone.utc).timestamp())
            })

        return ret

    def get_gyms_changed_since(self, timestamp):
        query = (
            "SELECT name, description, url, gym.gym_id, team_id, "
            "guard_pokemon_id, slots_available, latitude, longitude, "
            "total_cp, is_in_battle, weather_boosted_condition, "
            "last_modified, gym.last_scanned, gym.is_ex_raid_eligible "
            "FROM gym "
            "LEFT JOIN gymdetails ON gym.gym_id = gymdetails.gym_id "
            "WHERE gym.last_scanned >= %s"
        )

        tsdt = datetime.utcfromtimestamp(
            timestamp).strftime("%Y-%m-%d %H:%M:%S")
        res = self.execute(query, (tsdt, ))
        ret = []

        for (name, description, url, gym_id, team_id, guard_pokemon_id, slots_available,
                latitude, longitude, total_cp, is_in_battle, weather_boosted_condition,
                last_modified, last_scanned, is_ex_raid_eligible) in res:
            ret.append({
                "gym_id": gym_id,
                "team_id": team_id,
                "guard_pokemon_id": guard_pokemon_id,
                "slots_available": slots_available,
                "latitude": latitude,
                "longitude": longitude,
                "total_cp": total_cp,
                "is_in_battle": is_in_battle,
                "weather_boosted_condition": weather_boosted_condition,
                "last_scanned": int(last_scanned.replace(tzinfo=timezone.utc).timestamp()),
                "last_modified": int(last_modified.replace(tzinfo=timezone.utc).timestamp()),
                "name": name,
                "url": url,
                "description": description,
                "is_ex_raid_eligible": is_ex_raid_eligible
            })

        return ret

    def __extract_args_single_pokestop_details(self, stop_data):
        if stop_data.get('type', 999) != 1:
            return None
        image = stop_data.get('image_urls', None)
        name = stop_data.get('name', None)
        now = datetime.utcfromtimestamp(
            time.time()).strftime("%Y-%m-%d %H:%M:%S")
        last_modified = '1970-01-01 00:00:00'

        return stop_data['fort_id'], 1, stop_data['latitude'], stop_data['longitude'], last_modified, now, name, image[0]

    def statistics_get_pokemon_count(self, minutes):
        logger.debug('Fetching pokemon spawns count from db')
        query_where = ''
        query_date = "UNIX_TIMESTAMP(DATE_FORMAT(last_modified, '%y-%m-%d %k:00:00')) as timestamp"
        if minutes:
            minutes = datetime.utcnow().replace(
                minute=0, second=0, microsecond=0) - timedelta(minutes=int(minutes))
            query_where = ' where last_modified > \'%s\' ' % str(minutes)

        query = (
            "SELECT  %s, count(DISTINCT encounter_id) as Count, if(CP is NULL, 0, 1) as IV FROM pokemon "
            " %s "
            "group by IV, day(TIMESTAMP(last_modified)), hour(TIMESTAMP(last_modified)) order by timestamp" %
                (str(query_date), str(query_where))
        )

        res = self.execute(query)

        return res

    def statistics_get_gym_count(self):
        logger.debug('Fetching gym count from db')

        query = (
            "SELECT if (team_id=0, 'WHITE', if (team_id=1, 'BLUE', if (team_id=2, 'RED', 'YELLOW'))) "
            "as Color, count(team_id) as Count FROM `gym` group by team_id"

        )

        res = self.execute(query)

        return res

    def statistics_get_stop_quest(self):
        logger.debug('Fetching gym count from db')

        query = (
            "SELECT "
            "if(FROM_UNIXTIME(trs_quest.quest_timestamp, '%y-%m-%d') is NULL,'NO QUEST',"
            "FROM_UNIXTIME(trs_quest.quest_timestamp, '%y-%m-%d')) as Quest, "
            "count(pokestop.pokestop_id) as Count FROM pokestop left join trs_quest "
            "on pokestop.pokestop_id = trs_quest.GUID "
            "group by FROM_UNIXTIME(trs_quest.quest_timestamp, '%y-%m-%d')"

        )
        res = self.execute(query)

        return res

    def get_pokemon_spawns(self, hours):
        logger.debug('Fetching pokemon spawns from db')
        query_where = ''
        if hours:
            hours = datetime.utcnow() - timedelta(hours=hours)
            query_where = ' where disappear_time > \'%s\' ' % str(hours)

        query = (
            "SELECT pokemon_id, count(pokemon_id) from pokemon %s group by pokemon_id" % str(
                query_where)
        )

        res = self.execute(query)

        total = reduce(lambda x, y: x + y[1], res, 0)

        return {'pokemon': res, 'total': total}

    def get_best_pokemon_spawns(self):
        logger.debug('Fetching best pokemon spawns from db')

        query = (
            "SELECT encounter_id, pokemon_id, unix_timestamp(last_modified),"
            " individual_attack, individual_defense, individual_stamina, cp_multiplier, cp"
            " FROM pokemon"
            " WHERE individual_attack>14 and individual_defense>14 and individual_stamina>14"
            " ORDER BY UNIX_TIMESTAMP(last_modified) DESC LIMIT 300"
        )

        res = self.execute(query)
        return res

    def delete_stop(self, latitude: float, longitude: float):
        logger.debug('Deleting stop from db')
        query = (
            "delete from pokestop where latitude=%s and longitude=%s"
        )
        del_vars = (latitude, longitude)
        self.execute(query, del_vars, commit=True)

    def get_gyms_in_rectangle(self, neLat, neLon, swLat, swLon, oNeLat=None, oNeLon=None, oSwLat=None, oSwLon=None, timestamp=None):
        gyms = {}

        # base query to fetch gyms
        query = (
            "SELECT gym.gym_id, gym.latitude, gym.longitude, "
            "gymdetails.name, gymdetails.url, gym.team_id, "
            "gym.last_modified, raid.level, raid.spawn, raid.start, "
            "raid.end, raid.pokemon_id, raid.form, gym.last_scanned "
            "FROM gym "
            "INNER JOIN gymdetails ON gym.gym_id = gymdetails.gym_id "
            "LEFT JOIN raid ON raid.gym_id = gym.gym_id "
        )

        # fetch gyms only in a certain rectangle
        query_where = (
            " WHERE (latitude >= {} AND longitude >= {} "
            " AND latitude <= {} AND longitude <= {}) "
        ).format(swLat, swLon, neLat, neLon)

        # but don't fetch gyms from a known rectangle
        if oNeLat is not None and oNeLon is not None and oSwLat is not None and oSwLon is not None:
            oquery_where = (
                " AND NOT (latitude >= {} AND longitude >= {} "
                " AND latitude <= {} AND longitude <= {}) "
            ).format(oSwLat, oSwLon, oNeLat, oNeLon)

            query_where = query_where + oquery_where

        # there's no old rectangle so check for a timestamp to send only updated stuff
        elif timestamp is not None:
            tsdt = datetime.utcfromtimestamp(int(timestamp)).strftime("%Y-%m-%d %H:%M:%S")

            # TODO ish: until we don't show any other information like raids
            #          we can use last_modified, since that will give us actual
            #          changes like gym color change
            oquery_where = " AND last_modified >= '{}' ".format(tsdt)

            query_where = query_where + oquery_where

        res = self.execute(query + query_where)

        for (gym_id, latitude, longitude, name, url, team_id, last_updated,
                level, spawn, start, end, mon_id, form, last_scanned) in res:

            nowts = datetime.utcfromtimestamp(time.time()).timestamp()

            # check if we found a raid and if it's still active
            if end is None or nowts > int(end.replace(tzinfo=timezone.utc).timestamp()):
                raid = None
            else:
                raid = {
                    "spawn": int(spawn.replace(tzinfo=timezone.utc).timestamp()),
                    "start": int(start.replace(tzinfo=timezone.utc).timestamp()),
                    "end": int(end.replace(tzinfo=timezone.utc).timestamp()),
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
                "team_id": team_id,
                "last_updated": int(last_updated.replace(tzinfo=timezone.utc).timestamp()),
                "last_scanned": int(last_scanned.replace(tzinfo=timezone.utc).timestamp()),
                "raid": raid
            }

        return gyms

    def check_stop_quest_level(self, worker, latitude, longitude):
        logger.debug("RmWrapper::check_stop_quest_level called")
        query = (
            "SELECT trs_stats_detect_raw.type_id "
            "from trs_stats_detect_raw inner join pokestop on pokestop.pokestop_id = trs_stats_detect_raw.type_id "
            "where pokestop.latitude=%s and pokestop.longitude=%s and trs_stats_detect_raw.worker=%s"
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

        now = datetime.utcfromtimestamp(time.time()).strftime("%Y-%m-%d %H:%M:%S")

        query = (
            "SELECT encounter_id, spawnpoint_id, pokemon_id, latitude, "
            "longitude, disappear_time, individual_attack, individual_defense, "
            "individual_stamina, move_1, move_2, cp, weight, "
            "height, gender, form, costume, weather_boosted_condition, "
            "last_modified "
            "FROM pokemon "
            "WHERE disappear_time > '{}'"
        ).format(now)

        query_where = (
            " AND (latitude >= {} AND longitude >= {} "
            " AND latitude <= {} AND longitude <= {}) "
        ).format(swLat, swLon, neLat, neLon)

        if oNeLat is not None and oNeLon is not None and oSwLat is not None and oSwLon is not None:
            oquery_where = (
                " AND NOT (latitude >= {} AND longitude >= {} "
                " AND latitude <= {} AND longitude <= {}) "
            ).format(oSwLat, oSwLon, oNeLat, oNeLon)

            query_where = query_where + oquery_where

        # there's no old rectangle so check for a timestamp to send only updated stuff
        elif timestamp is not None:
            tsdt = datetime.utcfromtimestamp(int(timestamp)).strftime("%Y-%m-%d %H:%M:%S")

            oquery_where = " AND last_modified >= '{}' ".format(tsdt)

            query_where = query_where + oquery_where

        res = self.execute(query + query_where)

        for (encounter_id, spawnpoint_id, pokemon_id, latitude, longitude,
                disappear_time, individual_attack, individual_defense,
                individual_stamina, move_1, move_2, cp,
                weight, height, gender, form, costume,
                weather_boosted_condition, last_modified) in res:

            mons.append({
                "encounter_id": encounter_id,
                "spawnpoint_id": spawnpoint_id,
                "mon_id": pokemon_id,
                "latitude": latitude,
                "longitude": longitude,
                "disappear_time": int(disappear_time.replace(tzinfo=timezone.utc).timestamp()),
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
                "last_modified": int(last_modified.replace(tzinfo=timezone.utc).timestamp())
            })

        return mons

    def statistics_get_shiny_stats(self):
        logger.debug('Fetching shiny pokemon stats from db')
        query = (
            "SELECT (select count(DISTINCT encounter_id) from pokemon inner join trs_stats_detect_raw on "
            "trs_stats_detect_raw.type_id=pokemon.encounter_id where pokemon.pokemon_id=a.pokemon_id and "
            "trs_stats_detect_raw.worker=b.worker and pokemon.form=a.form), count(DISTINCT encounter_id), a.pokemon_id,"
            "b.worker, GROUP_CONCAT(DISTINCT encounter_id ORDER BY encounter_id DESC SEPARATOR '<br>'), a.form "
            "FROM pokemon a left join trs_stats_detect_raw b on a.encounter_id=CAST(b.type_id as unsigned int) where b.is_shiny=1 group by "
            "b.is_shiny, a.pokemon_id, a.form, b.worker order by a.pokemon_id"
        )

        res = self.execute(query)

        return res
