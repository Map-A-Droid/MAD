import json
import sys
import time
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from multiprocessing import Lock, Semaphore
from typing import List, Optional

import mysql
from bitstring import BitArray
from mysql.connector.pooling import MySQLConnectionPool

from utils.collections import Location
from utils.logging import logger
from utils.questGen import questtask
from utils.s2Helper import S2Helper


class DbWrapperBase(ABC):
    def_spawn = 240

    def __init__(self, args):
        self.application_args = args
        self.host = args.dbip
        self.port = args.dbport
        self.user = args.dbusername
        self.password = args.dbpassword
        self.database = args.dbname
        self.pool = None
        self.pool_mutex = Lock()
        self.connection_semaphore = Semaphore(
            self.application_args.db_poolsize)
        self.dbconfig = {"database": self.database, "user": self.user, "host": self.host, "password": self.password,
                         "port": self.port}
        self._init_pool()

    def _init_pool(self):
        logger.info("Connecting to DB")
        self.pool_mutex.acquire()
        self.pool = MySQLConnectionPool(pool_name="db_wrapper_pool",
                                        pool_size=self.application_args.db_poolsize,
                                        **self.dbconfig)
        self.pool_mutex.release()

    def check_index_exists(self, table, index):
        query = (
            "SELECT count(*) "
            "FROM information_schema.statistics "
            "WHERE table_name = %s "
            "AND index_name = %s "
            "AND table_schema = %s"
        )
        vals = (
            table,
            index,
            self.database,
        )

        return int(self.execute(query, vals)[0][0])

    def check_column_exists(self, table, column):
        query = (
            "SELECT count(*) "
            "FROM information_schema.columns "
            "WHERE table_name = %s "
            "AND column_name = %s "
            "AND table_schema = %s"
        )
        vals = (
            table,
            column,
            self.database,
        )

        return int(self.execute(query, vals)[0][0])

    def _check_create_column(self, field):
        if self.check_column_exists(field["table"], field["column"]) == 1:
            return

        alter_query = (
            "ALTER TABLE {} "
            "ADD COLUMN {} {}"
            .format(field["table"], field["column"], field["ctype"])
        )

        self.execute(alter_query, commit=True)

        if self.check_column_exists(field["table"], field["column"]) == 1:
            logger.info("Successfully added '{}.{}' column",
                        field["table"], field["column"])
            return
        else:
            logger.error("Couldn't create required column {}.{}'",
                         field["table"], field["column"])
            sys.exit(1)

    def close(self, conn, cursor):
        """
        A method used to close connection of mysql.
        :param conn:
        :param cursor:
        :return:
        """
        cursor.close()
        conn.close()

    def execute(self, sql, args=None, commit=False):
        """
        Execute a sql, it could be with args and with out args. The usage is
        similar with execute() function in module pymysql.
        :param sql: sql clause
        :param args: args need by sql clause
        :param commit: whether to commit
        :return: if commit, return None, else, return result
        """
        self.connection_semaphore.acquire()
        conn = self.pool.get_connection()
        cursor = conn.cursor()

        # TODO: consider catching OperationalError
        # try:
        #     cursor = conn.cursor()
        # except OperationalError as e:
        #     logger.error("OperationalError trying to acquire a DB cursor: {}", str(e))
        #     conn.rollback()
        #     return None
        try:
            if args:
                cursor.execute(sql, args)
            else:
                cursor.execute(sql)
            if commit is True:
                affected_rows = cursor.rowcount
                conn.commit()
                return affected_rows
            else:
                res = cursor.fetchall()
                return res
        except mysql.connector.Error as err:
            logger.error("Failed executing query: {}, error: {}", str(sql), str(err))
            return None
        except Exception as e:
            logger.error("Unspecified exception in dbWrapper: {}", str(e))
            return None
        finally:
            self.close(conn, cursor)
            self.connection_semaphore.release()

    def executemany(self, sql, args, commit=False):
        """
        Execute with many args. Similar with executemany() function in pymysql.
        args should be a sequence.
        :param sql: sql clause
        :param args: args
        :param commit: commit or not.
        :return: if commit, return None, else, return result
        """
        # get connection form connection pool instead of create one.
        self.connection_semaphore.acquire()
        conn = self.pool.get_connection()
        cursor = conn.cursor()

        try:
            cursor.executemany(sql, args)

            if commit is True:
                conn.commit()
                return None
            else:
                res = cursor.fetchall()
                return res
        except mysql.connector.Error as err:
            logger.error("Failed executing query: {}", str(err))
            return None
        except Exception as e:
            logger.error("Unspecified exception in dbWrapper: {}", str(e))
            return None
        finally:
            self.close(conn, cursor)
            self.connection_semaphore.release()

    @abstractmethod
    def get_next_raid_hatches(self, delay_after_hatch, geofence_helper=None):
        """
        In order to build a priority queue, we need to be able to check for the next hatches of raid eggs
        The result may not be sorted by priority, to be done at a higher level!
        :return: unsorted list of next hatches within delay_after_hatch
        """
        pass

    @abstractmethod
    def set_scanned_location(self, lat, lng, capture_time):
        """
        Update scannedlocation (in RM) of a given lat/lng
        """
        pass

    @abstractmethod
    def check_stop_quest(self, lat, lng):
        """
        Update scannedlocation (in RM) of a given lat/lng
        """
        pass

    @abstractmethod
    def gyms_from_db(self, geofence_helper):
        """
        Retrieve all the gyms valid within the area set by geofence_helper
        :return: numpy array with coords
        """
        pass

    @abstractmethod
    def update_encounters_from_db(self, geofence_helper, latest=0):
        """
        Retrieve all encountered ids inside the geofence.
        :return: the new value of latest and a dict like encounter_id: disappear_time
        """
        pass

    @abstractmethod
    def stops_from_db(self, geofence_helper):
        """
        Retrieve all the pokestops valid within the area set by geofence_helper
        :return: numpy array with coords
        """
        pass

    @abstractmethod
    def quests_from_db(self, GUID=None, timestamp=None):
        """
        Retrieve all the pokestops valid within the area set by geofence_helper
        :return: numpy array with coords
        """
        pass

    @abstractmethod
    def submit_mon_iv(self, origin: str, timestamp: float, encounter_proto: dict, mitm_mapper):
        """
        Update/Insert a mon with IVs
        """
        pass

    @abstractmethod
    def submit_mons_map_proto(self, origin: str, map_proto: dict, mon_ids_iv: Optional[List[int]],
                              mitm_mapper):
        """
        Update/Insert mons from a map_proto dict
        """
        pass

    @abstractmethod
    def submit_pokestops_map_proto(self, origin, map_proto):
        """
        Update/Insert pokestops from a map_proto dict
        """
        pass

    @abstractmethod
    def submit_pokestops_details_map_proto(self, map_proto):
        """
        Update/Insert pokestop details from a GMO
        :param map_proto:
        :return:
        """
        pass

    @abstractmethod
    def submit_gyms_map_proto(self, origin, map_proto):
        """
        Update/Insert gyms from a map_proto dict
        """
        pass

    @abstractmethod
    def submit_gym_proto(self, origin, map_proto):
        """
        Update gyms from a map_proto dict
        """
        pass

    @abstractmethod
    def submit_raids_map_proto(self, origin: str, map_proto: dict, mitm_mapper):
        """
        Update/Insert raids from a map_proto dict
        """
        pass

    @abstractmethod
    def get_pokemon_spawns(self, hours):
        """
        Get Pokemon Spawns for dynamic rarity
        """
        pass

    @abstractmethod
    def submit_weather_map_proto(self, origin, map_proto, received_timestamp):
        """
        Update/Insert weather from a map_proto dict
        """
        pass

    @abstractmethod
    def get_to_be_encountered(self, geofence_helper, min_time_left_seconds, eligible_mon_ids):
        pass

    @abstractmethod
    def stop_from_db_without_quests(self, geofence_helper, levelmode: bool = False):
        pass

    @abstractmethod
    def get_raids_changed_since(self, timestamp):
        pass

    @abstractmethod
    def get_stops_changed_since(self, timestamp):
        pass

    @abstractmethod
    def get_mon_changed_since(self, timestamp):
        pass

    @abstractmethod
    def check_stop_quest_level(self, worker, latitude, longitude):
        pass

    @abstractmethod
    def get_quests_changed_since(self, timestamp):
        pass

    @abstractmethod
    def get_gyms_changed_since(self, timestamp):
        pass

    @abstractmethod
    def get_weather_changed_since(self, timestamp):
        pass

    @abstractmethod
    def get_gyms_in_rectangle(self, neLat, neLon, swLat, swLon,
                              oNeLat=None, oNeLon=None, oSwLat=None, oSwLon=None, timestamp=None):
        """
        Basically just for MADmin map. This method returns gyms within a certain rectangle.
        It also handles a diff/old area to reduce returned data. Also checks for updated
        elements withing the rectangle via the timestamp.
        """
        pass

    @abstractmethod
    def get_mons_in_rectangle(self, neLat, neLon, swLat, swLon,
                              oNeLat=None, oNeLon=None, oSwLat=None, oSwLon=None, timestamp=None):
        pass

    def statistics_get_pokemon_count(self, days):
        pass

    @abstractmethod
    def statistics_get_gym_count(self, days):
        pass

    @abstractmethod
    def statistics_get_stop_quest(self, days):
        pass

    @abstractmethod
    def get_best_pokemon_spawns(self):
        pass

    @abstractmethod
    def statistics_get_shiny_stats(self):
        pass

    @abstractmethod
    def delete_stop(self, lat: float, lng: float):
        pass

    def create_quest_database_if_not_exists(self):
        """
        In order to store 'hashes' of crops/images, we require a table to store those hashes
        """
        logger.debug(
            "DbWrapperBase::create_quest_database_if_not_exists called")
        logger.debug('Creating hash db in database')

        query = (' Create table if not exists trs_quest ( ' +
                 ' GUID varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL,' +
                 ' quest_type tinyint(3) NOT NULL, ' +
                 ' quest_timestamp int(11) NOT NULL,' +
                 ' quest_stardust smallint(4) NOT NULL,' +
                 ' quest_pokemon_id smallint(4) NOT NULL,' +
                 ' quest_reward_type smallint(3) NOT NULL,' +
                 ' quest_item_id smallint(3) NOT NULL,' +
                 ' quest_item_amount tinyint(2) NOT NULL,' +
                 ' quest_target tinyint(3) NOT NULL,' +
                 ' quest_condition varchar(500), ' +
                 ' PRIMARY KEY (GUID), ' +
                 ' KEY quest_type (quest_type))')
        self.execute(query, commit=True)

        return True

    def getspawndef(self, spawn_id):
        if not spawn_id:
            return False
        logger.debug("DbWrapperBase::getspawndef called")

        spawnids = ",".join(map(str, spawn_id))
        spawnret = {}

        query = (
            "SELECT spawnpoint, spawndef "
            "FROM trs_spawn where spawnpoint in (%s)" % (spawnids)
        )
        # vals = (spawn_id,)

        res = self.execute(query)
        for row in res:
            spawnret[int(row[0])] = row[1]
        return spawnret

    def submit_spawnpoints_map_proto(self, origin, map_proto):
        logger.debug(
            "DbWrapperBase::submit_spawnpoints_map_proto called with data received by {}", str(origin))
        cells = map_proto.get("cells", None)
        if cells is None:
            return False
        spawnpoint_args, spawnpoint_args_unseen = [], []
        spawnids = []

        query_spawnpoints = (
            "INSERT INTO trs_spawn (spawnpoint, latitude, longitude, earliest_unseen, "
            "last_scanned, spawndef, calc_endminsec) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s) "
            "ON DUPLICATE KEY UPDATE last_scanned=VALUES(last_scanned), "
            "earliest_unseen=LEAST(earliest_unseen, VALUES(earliest_unseen)), "
            "spawndef=VALUES(spawndef), calc_endminsec=VALUES(calc_endminsec)"
            ""
        )

        query_spawnpoints_unseen = (
            "INSERT INTO trs_spawn (spawnpoint, latitude, longitude, earliest_unseen, last_non_scanned, spawndef) "
            "VALUES (%s, %s, %s, %s, %s, %s) "
            "ON DUPLICATE KEY UPDATE spawndef=VALUES(spawndef), last_non_scanned=VALUES(last_non_scanned)"
            ""
        )

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        dt = datetime.now()

        for cell in cells:
            for wild_mon in cell["wild_pokemon"]:
                spawnids.append(int(str(wild_mon['spawnpoint_id']), 16))

        spawndef = self.getspawndef(spawnids)

        for cell in cells:
            for wild_mon in cell["wild_pokemon"]:
                spawnid = int(str(wild_mon['spawnpoint_id']), 16)
                lat, lng, alt = S2Helper.get_position_from_cell(
                    int(str(wild_mon['spawnpoint_id']) + '00000', 16))
                despawntime = wild_mon['time_till_hidden']

                minpos = self._get_min_pos_in_array()
                # TODO: retrieve the spawndefs by a single executemany and pass that...

                spawndef_ = spawndef.get(spawnid, False)
                if spawndef_:
                    newspawndef = self._set_spawn_see_minutesgroup(
                        spawndef_, minpos)
                else:
                    newspawndef = self._set_spawn_see_minutesgroup(
                        DbWrapperBase.def_spawn, minpos)

                last_scanned = None
                last_non_scanned = None

                if 0 <= int(despawntime) <= 90000:
                    fulldate = dt + timedelta(milliseconds=despawntime)
                    earliest_unseen = int(despawntime)
                    last_scanned = now
                    calcendtime = fulldate.strftime("%M:%S")

                    spawnpoint_args.append(
                        (
                            spawnid, lat, lng, earliest_unseen, last_scanned, newspawndef, calcendtime
                        )
                    )

                else:
                    earliest_unseen = 99999999
                    last_non_scanned = now
                    calcendtime = None

                    spawnpoint_args_unseen.append(
                        (
                            spawnid, lat, lng, earliest_unseen, last_non_scanned, newspawndef
                        )
                    )

        self.executemany(query_spawnpoints, spawnpoint_args, commit=True)
        self.executemany(query_spawnpoints_unseen,
                         spawnpoint_args_unseen, commit=True)

    def get_detected_spawns(self, geofence_helper) -> List[Location]:
        logger.debug("DbWrapperBase::get_detected_spawns called")

        minLat, minLon, maxLat, maxLon = geofence_helper.get_polygon_from_fence()

        query = (
            "SELECT latitude, longitude "
            "FROM trs_spawn "
            "WHERE (latitude >= {} AND longitude >= {} "
            "AND latitude <= {} AND longitude <= {}) "
        ).format(minLat, minLon, maxLat, maxLon)

        list_of_coords: List[Location] = []
        logger.debug(
            "DbWrapperBase::get_detected_spawns executing select query")
        res = self.execute(query)
        logger.debug(
            "DbWrapperBase::get_detected_spawns result of query: {}", str(res))
        for (latitude, longitude) in res:
            list_of_coords.append(Location(latitude, longitude))

        if geofence_helper is not None:
            logger.debug(
                "DbWrapperBase::get_detected_spawns applying geofence")
            geofenced_coords = geofence_helper.get_geofenced_coordinates(
                list_of_coords)
            logger.debug(geofenced_coords)
            return geofenced_coords
        else:
            logger.debug(
                "DbWrapperBase::get_detected_spawns converting to numpy")
            # to_return = np.zeros(shape=(len(list_of_coords), 2))
            # for i in range(len(to_return)):
            #     to_return[i][0] = list_of_coords[i][0]
            #     to_return[i][1] = list_of_coords[i][1]
            return list_of_coords

    def get_undetected_spawns(self, geofence_helper):
        logger.debug("DbWrapperBase::get_undetected_spawns called")

        query = (
            "SELECT latitude, longitude "
            "FROM trs_spawn "
            "WHERE calc_endminsec is NULL"
        )
        list_of_coords: List[Location] = []
        logger.debug(
            "DbWrapperBase::get_undetected_spawns executing select query")
        res = self.execute(query)
        logger.debug(
            "DbWrapperBase::get_undetected_spawns result of query: {}", str(res))
        for (latitude, longitude) in res:
            list_of_coords.append(Location(latitude, longitude))

        if geofence_helper is not None:
            logger.debug(
                "DbWrapperBase::get_undetected_spawns applying geofence")
            geofenced_coords = geofence_helper.get_geofenced_coordinates(
                list_of_coords)
            logger.debug(geofenced_coords)
            return geofenced_coords
        else:
            logger.debug(
                "DbWrapperBase::get_undetected_spawns converting to numpy")
            # to_return = np.zeros(shape=(len(list_of_coords), 2))
            # for i in range(len(to_return)):
            #     to_return[i][0] = list_of_coords[i][0]
            #     to_return[i][1] = list_of_coords[i][1]
            return list_of_coords

    def get_detected_endtime(self, spawn_id):
        logger.debug("DbWrapperBase::get_detected_endtime called")

        query = (
            "SELECT calc_endminsec "
            "FROM trs_spawn "
            "WHERE spawnpoint=%s"
        )
        args = (
            spawn_id,
        )

        found = self.execute(query, args)

        if found and len(found) > 0 and found[0][0]:
            return str(found[0][0])
        else:
            return False

    def _get_min_pos_in_array(self):
        min = datetime.now().strftime("%M")

        if 0 <= int(min) < 15:
            pos = 4
        elif 15 <= int(min) < 30:
            pos = 5
        elif 30 <= int(min) < 45:
            pos = 6
        elif 45 <= int(min) < 60:
            pos = 7
        else:
            pos = None

        self.__globaldef = pos

        return pos

    def _set_spawn_see_minutesgroup(self, spawndef, pos):
        # b = BitArray([int(digit) for digit in bin(spawndef)[2:]])
        b = BitArray(uint=spawndef, length=8)
        if pos == 4:
            b[0] = 0
            b[4] = 1
        if pos == 5:
            b[1] = 0
            b[5] = 1
        if pos == 6:
            b[2] = 0
            b[6] = 1
        if pos == 7:
            b[3] = 0
            b[7] = 1
        return b.uint

    def check_and_create_spawn_tables(self):
        logger.debug("DbWrapperBase::check_and_create_spawn_tables called")

        query_trs_spawn = ('CREATE TABLE IF NOT EXISTS `trs_spawn` ('
                           '`spawnpoint` varchar(16) COLLATE utf8mb4_unicode_ci NOT NULL, '
                           '`latitude` double NOT NULL, '
                           '`longitude` double NOT NULL, '
                           '`spawndef` int(11) NOT NULL DEFAULT "240", '
                           '`earliest_unseen` int(6) NOT NULL, '
                           '`last_scanned` datetime DEFAULT NULL, '
                           '`first_detection` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP, '
                           '`last_non_scanned` datetime DEFAULT NULL, '
                           '`calc_endminsec` varchar(5) COLLATE utf8mb4_unicode_ci DEFAULT NULL, '
                           'UNIQUE KEY `spawnpoint_2` (`spawnpoint`), '
                           'KEY `spawnpoint` (`spawnpoint`) '
                           ') ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;'
                           )

        query_trs_spawnsightings = ('CREATE TABLE IF NOT EXISTS `trs_spawnsightings` ('
                                    '`id` int(11) NOT NULL AUTO_INCREMENT, '
                                    '`encounter_id` bigint(20) UNSIGNED NOT NULL, '
                                    '`spawnpoint_id` bigint(20) UNSIGNED NOT NULL, '
                                    '`scan_time` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP, '
                                    '`tth_secs` int(11) DEFAULT NULL, '
                                    'PRIMARY KEY (`id`), '
                                    'KEY `trs_spawnpointdd_spawnpoint_id` (`spawnpoint_id`) '
                                    ') ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;'
                                    )

        self.execute(query_trs_spawn, commit=True)
        self.execute(query_trs_spawnsightings, commit=True)

    def download_spawns(self, neLat=None, neLon=None, swLat=None, swLon=None, oNeLat=None, oNeLon=None,
                        oSwLat=None, oSwLon=None, timestamp=None, fence=None):
        logger.debug("dbWrapper::download_spawns")
        spawn = {}
        query_where = ""

        query = (
            "SELECT spawnpoint, latitude, longitude, calc_endminsec, "
            "spawndef, last_scanned, first_detection, last_non_scanned "
            "FROM `trs_spawn`"
        )

        if neLat is not None:
            query_where = (
                " WHERE (latitude >= {} AND longitude >= {} "
                " AND latitude <= {} AND longitude <= {}) "
            ).format(swLat, swLon, neLat, neLon)

        if oNeLat is not None and oNeLon is not None and oSwLat is not None and oSwLon is not None:
            oquery_where = (
                " AND NOT (latitude >= {} AND longitude >= {} "
                " AND latitude <= {} AND longitude <= {}) "
            ).format(oSwLat, oSwLon, oNeLat, oNeLon)

            query_where = query_where + oquery_where
        elif timestamp is not None:
            tsdt = datetime.utcfromtimestamp(int(timestamp)).strftime("%Y-%m-%d %H:%M:%S")

            oquery_where = (
                " AND last_scanned >= '{}' "
            ).format(tsdt)

            query_where = query_where + oquery_where

        if fence is not None:
            query_where = query_where + " where ST_CONTAINS(ST_GEOMFROMTEXT( 'POLYGON(( {} ))'), " \
                                        "POINT(trs_spawn.latitude, trs_spawn.longitude))".format(str(fence))

        query = query + query_where
        res = self.execute(query)

        for (spawnid, lat, lon, endtime, spawndef, last_scanned, first_detection, last_non_scanned) in res:
            spawn[spawnid] = {
                'id': spawnid,
                'lat': lat,
                'lon': lon,
                'endtime': endtime,
                'spawndef': spawndef,
                'lastscan': str(last_scanned),
                'lastnonscan': str(last_non_scanned),
                'first_detection': str(first_detection)
            }

        return str(json.dumps(spawn))

    def retrieve_next_spawns(self, geofence_helper):
        """
        Retrieve the spawnpoints with their respective unixtimestamp that are due in the next 300 seconds
        :return:
        """

        logger.debug("DbWrapperBase::retrieve_next_spawns called")

        current_time_of_day = datetime.now().replace(microsecond=0)
        minLat, minLon, maxLat, maxLon = geofence_helper.get_polygon_from_fence()

        query = (
            "SELECT latitude, longitude, spawndef, calc_endminsec "
            "FROM trs_spawn "
            "WHERE calc_endminsec IS NOT NULL "
            "AND (latitude >= {} AND longitude >= {} AND latitude <= {} AND longitude <= {}) "
            "AND DATE_FORMAT(STR_TO_DATE(calc_endminsec,'%i:%s'),'%i:%s') BETWEEN DATE_FORMAT(DATE_ADD(NOW(), "
            " INTERVAL if(spawndef=15,60,30) MINUTE),'%i:%s') "
            "AND DATE_FORMAT(DATE_ADD(NOW(), INTERVAL if(spawndef=15,70,40) MINUTE),'%i:%s')"
        ).format(minLat, minLon, maxLat, maxLon)

        res = self.execute(query)
        next_up = []
        current_time = time.time()
        for (latitude, longitude, spawndef, calc_endminsec) in res:
            if geofence_helper and not geofence_helper.is_coord_inside_include_geofence([latitude, longitude]):
                continue
            endminsec_split = calc_endminsec.split(":")
            minutes = int(endminsec_split[0])
            seconds = int(endminsec_split[1])
            temp_date = current_time_of_day.replace(
                minute=minutes, second=seconds)
            if minutes < datetime.now().minute:
                temp_date = temp_date + timedelta(hours=1)

            if temp_date < current_time_of_day:
                # spawn has already happened, we should've added it in the past, let's move on
                # TODO: consider crosschecking against current mons...
                continue

            spawn_duration_minutes = 60 if spawndef == 15 else 30

            timestamp = time.mktime(temp_date.timetuple()) - \
                spawn_duration_minutes * 60
            # check if we calculated a time in the past, if so, add an hour to it...
            timestamp = timestamp + 60 * 60 if timestamp < current_time else timestamp
            # TODO: consider the following since I am not sure if the prio Q clustering handles stuff properly yet
            # if timestamp >= current_time + 600:
            #     # let's skip monspawns that are more than 10minutes in the future
            #     continue
            next_up.append(
                (
                    timestamp, Location(latitude, longitude)
                )
            )
        return next_up

    def submit_quest_proto(self, origin: str, map_proto: dict, mitm_mapper):
        logger.debug("DbWrapperBase::submit_quest_proto called")
        fort_id = map_proto.get("fort_id", None)
        if fort_id is None:
            return False
        if 'challenge_quest' not in map_proto:
            return False
        quest_type = map_proto['challenge_quest']['quest'].get(
            "quest_type", None)
        quest_template = map_proto['challenge_quest']['quest'].get(
            "template_id", None)
        if map_proto['challenge_quest']['quest'].get("quest_rewards", None):
            rewardtype = map_proto['challenge_quest']['quest']['quest_rewards'][0].get(
                "type", None)
            reward = map_proto['challenge_quest']['quest'].get(
                "quest_rewards", None)
            item = map_proto['challenge_quest']['quest']['quest_rewards'][0]['item'].get(
                "item", None)
            itemamount = map_proto['challenge_quest']['quest']['quest_rewards'][0]['item'].get(
                "amount", None)
            stardust = map_proto['challenge_quest']['quest']['quest_rewards'][0].get(
                "stardust", None)
            pokemon_id = map_proto['challenge_quest']['quest']['quest_rewards'][0]['pokemon_encounter'].get(
                "pokemon_id", None)
            target = map_proto['challenge_quest']['quest']['goal'].get(
                "target", None)
            condition = map_proto['challenge_quest']['quest']['goal'].get(
                "condition", None)

            json_condition = json.dumps(condition)
            task = questtask(int(quest_type), json_condition, int(target))
            mitm_mapper.collect_quest_stats(origin, fort_id)

            query_quests = (
                "INSERT INTO trs_quest (GUID, quest_type, quest_timestamp, quest_stardust, quest_pokemon_id, "
                "quest_reward_type, quest_item_id, quest_item_amount, quest_target, quest_condition, quest_reward, "
                "quest_task, quest_template) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
                "ON DUPLICATE KEY UPDATE quest_type=VALUES(quest_type), quest_timestamp=VALUES(quest_timestamp), "
                "quest_stardust=VALUES(quest_stardust), quest_pokemon_id=VALUES(quest_pokemon_id), "
                "quest_reward_type=VALUES(quest_reward_type), quest_item_id=VALUES(quest_item_id), "
                "quest_item_amount=VALUES(quest_item_amount), quest_target=VALUES(quest_target), "
                "quest_condition=VALUES(quest_condition), quest_reward=VALUES(quest_reward), "
                "quest_task=VALUES(quest_task), quest_template=VALUES(quest_template)"
            )
            vals = (
                fort_id, quest_type, time.time(
                ), stardust, pokemon_id, rewardtype, item, itemamount, target,
                json_condition, json.dumps(reward), task, quest_template
            )
            logger.debug("DbWrapperBase::submit_quest_proto submitted quest typ {} at stop {}", str(
                quest_type), str(fort_id))
            self.execute(query_quests, vals, commit=True)

        return True

    def create_status_database_if_not_exists(self):
        logger.debug(
            "DbWrapperBase::create_status_database_if_not_exists called")

        query = (' Create table if not exists trs_status (  '
                 'origin VARCHAR(50) NOT NULL , '
                 ' currentPos VARCHAR(50) NULL DEFAULT NULL, '
                 ' lastPos VARCHAR(50) NULL DEFAULT NULL, '
                 ' routePos INT(11) NULL DEFAULT NULL, '
                 ' routeMax INT(11) NULL DEFAULT NULL, '
                 ' routemanager VARCHAR(255) NULL DEFAULT NULL, '
                 ' rebootCounter INT(11) NULL DEFAULT NULL, '
                 ' lastProtoDateTime VARCHAR(50) NULL DEFAULT NULL, '
                 ' lastPogoRestart VARCHAR(50) NULL DEFAULT NULL, '
                 ' init TEXT NOT NULL, '
                 ' rebootingOption TEXT NOT NULL, '
                 ' restartCounter TEXT NOT NULL, '
                 ' globalrestartcount INT(11) NULL DEFAULT 0, '
                 ' lastPogoReboot VARCHAR(50) NULL DEFAULT NULL , '
                 ' globalrebootcount INT(11) NULL DEFAULT 0, '
                 ' currentSleepTime INT(11) NOT NULL DEFAULT 0, '
                 ' PRIMARY KEY (origin))')

        self.execute(query, commit=True)

        return True

    def create_statistics_databases_if_not_exists(self):
        logger.debug(
            "DbWrapperBase::create_statistics_databases_if_not_exists called")

        query = ('CREATE TABLE if not exists trs_stats_location_raw ( '
                 ' id int(11) AUTO_INCREMENT,'
                 ' worker varchar(100) NOT NULL,'
                 ' lat double NOT NULL,'
                 ' lng double NOT NULL,'
                 ' fix_ts int(11) NOT NULL,'
                 ' data_ts int(11) NOT NULL,'
                 ' type tinyint(1) NOT NULL,'
                 ' walker varchar(255) NOT NULL,'
                 ' success tinyint(1) NOT NULL,'
                 ' period int(11) NOT NULL, '
                 ' count int(11) NOT NULL, '
                 ' transporttype tinyint(1) NOT NULL, '
                 ' PRIMARY KEY (id),'
                 ' KEY latlng (lat, lng),'
                 ' UNIQUE count_same_events (worker, lat, lng, type, period))'
                 )

        self.execute(query, commit=True)

        query = ('CREATE TABLE if not exists trs_stats_location ('
                 ' id int(11) AUTO_INCREMENT,'
                 ' worker varchar(100) NOT NULL,'
                 ' timestamp_scan int(11) NOT NULL,'
                 ' location_count int(11) NOT NULL,'
                 ' location_ok int(11) NOT NULL,'
                 ' location_nok int(11) NOT NULL, '
                 ' PRIMARY KEY (id),'
                 ' KEY worker (worker))'
                 )

        self.execute(query, commit=True)

        query = ('CREATE TABLE if not exists trs_stats_detect_raw ('
                 ' id int(11) AUTO_INCREMENT,'
                 ' worker varchar(100) NOT NULL,'
                 ' type_id varchar(100) NOT NULL,'
                 ' type varchar(10) NOT NULL,'
                 ' count int(11) NOT NULL,'
                 ' timestamp_scan int(11) NOT NULL,'
                 ' PRIMARY KEY (id),'
                 ' KEY worker (worker))'
                 )

        self.execute(query, commit=True)

        query = ('CREATE TABLE if not exists trs_stats_detect ('
                 ' id  int(100) AUTO_INCREMENT,'
                 ' worker  varchar(100) NOT NULL,'
                 ' timestamp_scan  int(11) NOT NULL,'
                 ' mon  int(255) DEFAULT NULL,'
                 ' raid  int(255) DEFAULT NULL,'
                 ' mon_iv  int(11) DEFAULT NULL,'
                 ' quest  int(100) DEFAULT NULL,'
                 ' PRIMARY KEY (id), '
                 ' KEY worker (worker))'
                 )

        self.execute(query, commit=True)

        return True

    def create_usage_database_if_not_exists(self):
        logger.debug(
            "DbWrapperBase::create_usage_database_if_not_exists called")

        query = ('CREATE TABLE if not exists trs_usage ( '
                 'usage_id INT(10) AUTO_INCREMENT , '
                 'instance varchar(100) NULL DEFAULT NULL, '
                 'cpu FLOAT NULL DEFAULT NULL , '
                 'memory FLOAT NULL DEFAULT NULL , '
                 'garbage INT(5) NULL DEFAULT NULL , '
                 'timestamp INT(11) NULL DEFAULT NULL, '
                 'PRIMARY KEY (usage_id))'
                 )

        self.execute(query, commit=True)

        return True

    def insert_usage(self, instance, cpu, mem, garbage, timestamp):
        logger.debug("dbWrapper::insert_usage")

        query = (
            "INSERT into trs_usage (instance, cpu, memory, garbage, timestamp) VALUES "
            "(%s, %s, %s, %s, %s)"
        )
        vals = (
            instance, cpu, mem, garbage, timestamp
        )
        self.execute(query, vals, commit=True)

        return

    def save_status(self, data):
        logger.debug("dbWrapper::save_status")

        query = (
            "INSERT into trs_status (origin, currentPos, lastPos, routePos, routeMax, "
            "routemanager, rebootCounter, lastProtoDateTime, "
            "init, rebootingOption, restartCounter, currentSleepTime) values "
            "(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
            "ON DUPLICATE KEY UPDATE currentPos=VALUES(currentPos), "
            "lastPos=VALUES(lastPos), routePos=VALUES(routePos), "
            "routeMax=VALUES(routeMax), routemanager=VALUES(routemanager), "
            "rebootCounter=VALUES(rebootCounter), lastProtoDateTime=VALUES(lastProtoDateTime), "
            "init=VALUES(init), rebootingOption=VALUES(rebootingOption), restartCounter=VALUES(restartCounter), "
            "currentSleepTime=VALUES(currentSleepTime)"
        )
        vals = (
            data["Origin"], str(data["CurrentPos"]), str(
                data["LastPos"]), data["RoutePos"], data["RouteMax"],
            data["Routemanager"], data["RebootCounter"], data["LastProtoDateTime"],
            data["Init"], data["RebootingOption"], data["RestartCounter"], data["CurrentSleepTime"]
        )
        self.execute(query, vals, commit=True)
        return

    def save_last_reboot(self, origin):
        logger.debug("dbWrapper::save_last_reboot")
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        query = (
            "insert into trs_status(origin, lastPogoReboot, globalrebootcount) "
            "values (%s, %s, %s) "
            "ON DUPLICATE KEY UPDATE lastPogoReboot=VALUES(lastPogoReboot), globalrebootcount=(globalrebootcount+1)"

        )

        vals = (
            origin,  now, 1
        )

        self.execute(query, vals, commit=True)
        return

    def save_last_restart(self, origin):
        logger.debug("dbWrapper::save_last_restart")
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        query = (

            "insert into trs_status(origin, lastPogoRestart, globalrestartcount) "
            "values (%s, %s, %s) "
            "ON DUPLICATE KEY UPDATE lastPogoRestart=VALUES(lastPogoRestart), globalrestartcount=(globalrestartcount+1)"

        )

        vals = (
            origin, now, 1
        )

        self.execute(query, vals, commit=True)
        return

    def download_status(self):
        logger.debug("dbWrapper::download_status")
        workerstatus = []

        query = (
            "SELECT origin, currentPos, lastPos, routePos, routeMax, "
            "routemanager, rebootCounter, lastProtoDateTime, lastPogoRestart, "
            "init, rebootingOption, restartCounter, globalrebootcount, globalrestartcount, lastPogoReboot, "
            "currentSleepTime "
            "FROM trs_status"
        )

        result = self.execute(query)
        for (origin, currentPos, lastPos, routePos, routeMax, routemanager,
                rebootCounter, lastProtoDateTime, lastPogoRestart, init, rebootingOption, restartCounter,
                globalrebootcount, globalrestartcount, lastPogoReboot, currentSleepTime) in result:
            status = {
                "origin": origin,
                "currentPos": currentPos,
                "lastPos": lastPos,
                "routePos": routePos,
                "routeMax": routeMax,
                "routemanager": routemanager,
                "rebootCounter": rebootCounter,
                "lastProtoDateTime": str(lastProtoDateTime) if lastProtoDateTime is not None else None,
                "lastPogoRestart": str(lastPogoRestart) if lastPogoRestart is not None else None,
                "init": init,
                "rebootingOption": rebootingOption,
                "restartCounter": restartCounter,
                "lastPogoReboot": lastPogoReboot,
                "globalrebootcount": globalrebootcount,
                "globalrestartcount": globalrestartcount,
                "currentSleepTime": currentSleepTime

            }

            workerstatus.append(status)

        return str(json.dumps(workerstatus, indent=4, sort_keys=True))

    def statistics_get_quests_count(self, days):
        logger.debug('Fetching quests count from db')
        query_where = ''
        query_date = "unix_timestamp(DATE_FORMAT(FROM_UNIXTIME(quest_timestamp), '%y-%m-%d %k:00:00'))"

        if days:
            days = datetime.utcnow() - timedelta(days=days)
            query_where = ' WHERE FROM_UNIXTIME(quest_timestamp) > \'%s\' ' % str(
                days)

        query = (
            "SELECT %s, count(GUID) as Count  FROM trs_quest %s "
            "group by day(FROM_UNIXTIME(quest_timestamp)), hour(FROM_UNIXTIME(quest_timestamp)) "
            "order by quest_timestamp" %
                (str(query_date), str(query_where))
        )

        res = self.execute(query)

        return res

    def statistics_get_usage_count(self, minutes=120, instance=None):
        logger.debug('Fetching usage from db')
        query_where = ''

        if minutes:
            days = datetime.now() - timedelta(minutes=int(minutes))
            query_where = ' WHERE FROM_UNIXTIME(timestamp) > \'%s\' ' % str(
                days)

        if instance is not None:
            query_where = query_where + \
                ' and instance = \'%s\' ' % str(instance)

        query = (
            "SELECT cpu, memory, garbage, timestamp, instance FROM trs_usage %s "
            "order by timestamp" %
                (str(query_where))
        )

        res = self.execute(query)

        return res

    def submit_stats_complete(self, data):
        query_status = (
            "INSERT INTO trs_stats_detect (worker, timestamp_scan, raid, mon, mon_iv, quest) "
            "VALUES (%s, %s, %s, %s, %s, %s) "
        )
        self.executemany(query_status, data, commit=True)
        return True

    def submit_stats_locations(self, data):
        query_status = (
            "INSERT IGNORE INTO trs_stats_location (worker, timestamp_scan, location_count, location_ok, location_nok) "
            "VALUES (%s, %s, %s, %s, %s) "
        )
        self.executemany(query_status, data, commit=True)
        return True

    def submit_stats_locations_raw(self, data):
        query_status = (
            "INSERT IGNORE INTO trs_stats_location_raw (worker, fix_ts, lat, lng, data_ts, type, walker, "
            "success, period, transporttype) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) "
            "ON DUPLICATE KEY UPDATE count=(count+1)"
        )
        self.executemany(query_status, data, commit=True)
        return True

    def submit_stats_detections_raw(self, data):
        query_status = (
            "INSERT IGNORE INTO trs_stats_detect_raw (worker, type_id, type, count, is_shiny, timestamp_scan) "
            "VALUES (%s, %s, %s, %s, %s, %s) "
        )
        self.executemany(query_status, data, commit=True)
        return True

    def statistics_get_detection_count(self, minutes=False, grouped=True, worker=False):
        logger.debug('Fetching group detection count from db')
        grouped_query = ""
        worker_where = ""
        if worker and minutes:
            worker_where = ' and worker = \'%s\' ' % str(worker)
        if worker and not minutes:
            worker_where = ' where worker = \'%s\' ' % str(worker)
        if grouped:
            grouped_query = ", day(FROM_UNIXTIME(timestamp_scan)), hour(FROM_UNIXTIME(timestamp_scan))"
        query_where = ''
        query_date = "unix_timestamp(DATE_FORMAT(from_unixtime(timestamp_scan), '%y-%m-%d %k:00:00'))"
        if minutes:
            minutes = datetime.now().replace(
                minute=0, second=0, microsecond=0) - timedelta(minutes=int(minutes))
            query_where = ' where (timestamp_scan) >= unix_timestamp(\'%s\') ' % str(minutes)

        query = (
            "SELECT  %s, worker, sum(mon) as Mon, sum(mon_iv) as MonIV, sum(raid) as Raids, sum(quest) as Quests FROM "
            "trs_stats_detect %s %s group by worker %s"
            " order by timestamp_scan" %
                (str(query_date), str(query_where), str(worker_where), str(grouped_query))
        )
        res = self.execute(query)

        return res

    def statistics_get_avg_data_time(self, minutes=False, grouped=True, worker=False):
        logger.debug('Fetching group detection count from db')
        grouped_query = ""
        query_where = ""
        worker_where = ""
        if worker:
            worker_where = ' and worker = \'%s\' ' % str(worker)
        if grouped:
            grouped_query = ", day(FROM_UNIXTIME(period)), hour(FROM_UNIXTIME(period)), transporttype"
        if minutes:
            minutes = datetime.now().replace(
                minute=0, second=0, microsecond=0) - timedelta(minutes=int(minutes))
            query_where = ' and (period) >= unix_timestamp(\'%s\') ' % str(minutes)

        query_date = "unix_timestamp(DATE_FORMAT(FROM_UNIXTIME(period), '%y-%m-%d %k:00:00'))"

        query = (
            "SELECT %s, if(transporttype=0,'Teleport',if(transporttype=1,'Walk', "
            "'other')), worker, count(fix_ts), avg(data_ts-fix_ts) as data_time, walker from trs_stats_location_raw "
            "where success=1 and type in (0,1) and (walker='mon_mitm' or walker='iv_mitm' or walker='pokestops') "
            "%s %s group by worker %s" %
            (str(query_date), (query_where), str(worker_where), str(grouped_query))
        )

        res = self.execute(query)

        return res

    def statistics_get_locations(self, minutes=False, grouped=True, worker=False):
        logger.debug('Fetching group locations count from db')
        grouped_query = ""
        query_where = ""
        worker_where = ""
        if worker and minutes:
            worker_where = ' and worker = \'%s\' ' % str(worker)
        if worker and not minutes:
            worker_where = ' where worker = \'%s\' ' % str(worker)
        if grouped:
            grouped_query = ", day(FROM_UNIXTIME(timestamp_scan)), hour(FROM_UNIXTIME(timestamp_scan))"
        if minutes:
            minutes = datetime.now().replace(
                minute=0, second=0, microsecond=0) - timedelta(minutes=int(minutes))
            query_where = ' where (timestamp_scan) >= unix_timestamp(\'%s\') ' % str(minutes)

        query_date = "unix_timestamp(DATE_FORMAT(FROM_UNIXTIME(timestamp_scan), '%y-%m-%d %k:00:00'))"

        query = (
            "SELECT %s, worker, sum(location_count), sum(location_ok), sum(location_nok) from trs_stats_location "
            " %s %s group by worker %s" %
            (str(query_date), (query_where), str(worker_where), str(grouped_query))
        )
        res = self.execute(query)

        return res

    def statistics_get_locations_dataratio(self, minutes=False, grouped=True, worker=False):
        logger.debug('Fetching group locations dataratio from db')
        grouped_query = ""
        query_where = ""
        worker_where = ""
        if worker and minutes:
            worker_where = ' and worker = \'%s\' ' % str(worker)
        if worker and not minutes:
            worker_where = ' where worker = \'%s\' ' % str(worker)
        if grouped:
            grouped_query = ", success, type"
        if minutes:
            minutes = datetime.now().replace(
                minute=0, second=0, microsecond=0) - timedelta(minutes=int(minutes))
            query_where = ' where (period) >= unix_timestamp(\'%s\') ' % str(minutes)

        query_date = "unix_timestamp(DATE_FORMAT(FROM_UNIXTIME(period), '%y-%m-%d %k:00:00'))"

        query = (
            "SELECT %s, worker, count(period), if(type=0,if(success=1,'OK-Normal','NOK-Normal'),"
            "if(success=1,'OK-PrioQ','NOK-PrioQ')) from trs_stats_location_raw "
            " %s %s and type in(0,1) group by worker %s" %
            (str(query_date), (query_where), str(worker_where), str(grouped_query))
        )

        res = self.execute(query)

        return res

    def statistics_get_all_empty_scanns(self):
        logger.debug('Fetching all empty locations from db')
        query = ("SELECT count(b.id) as Count, b.lat, b.lng, GROUP_CONCAT(DISTINCT b.worker order by worker asc "
                 "SEPARATOR ', '), if(b.type=0,'Normal','PrioQ'), max(b.period), (select count(c.id) "
                 "from trs_stats_location_raw c where c.lat=b.lat and c.lng=b.lng and c.success=1) as successcount from "
                 "trs_stats_location_raw b where success=0 group by lat, lng HAVING Count > 5 and successcount=0 "
                 "ORDER BY count(id) DESC"
                 )

        res = self.execute(query)
        return res

    def statistics_get_detection_raw(self, minutes=False, worker=False):
        logger.debug('Fetching detetion raw data from db')
        query_where = ""
        worker_where = ""
        if worker and minutes:
            worker_where = ' and worker = \'%s\' ' % str(worker)
        if worker and not minutes:
            worker_where = ' where worker = \'%s\' ' % str(worker)
        if minutes:
            minutes = datetime.now().replace(
                minute=0, second=0, microsecond=0) - timedelta(minutes=int(minutes))
            query_where = ' where (timestamp_scan) >= unix_timestamp(\'%s\') ' % str(minutes)

        query_date = "unix_timestamp(DATE_FORMAT(FROM_UNIXTIME(timestamp_scan), '%y-%m-%d %k:00:00'))"

        query = (
            "SELECT %s, type, type_id, count FROM trs_stats_detect_raw %s %s order by id asc" %
            (str(query_date), (query_where), str(worker_where))
        )

        res = self.execute(query)
        return res

    def statistics_get_location_raw(self, minutes=False, worker=False):
        logger.debug('Fetching locations raw data from db')
        query_where = ""
        worker_where = ""
        if worker and minutes:
            worker_where = ' and worker = \'%s\' ' % str(worker)
        if worker and not minutes:
            worker_where = ' where worker = \'%s\' ' % str(worker)
        if minutes:
            minutes = datetime.now().replace(
                minute=0, second=0, microsecond=0) - timedelta(minutes=int(minutes))
            query_where = ' where (period) >= unix_timestamp(\'%s\') ' % str(minutes)

        query_date = "unix_timestamp(DATE_FORMAT(FROM_UNIXTIME(period), '%y-%m-%d %k:00:00'))"

        query = ("SELECT %s, lat, lng, if(type=0,'Normal',if(type=1,'PrioQ', if(type=2,'Startup',"
                 "if(type=3,'Reboot','Restart')))), if(success=1,'OK','NOK'), fix_ts, "
                 "if(data_ts=0,fix_ts,data_ts), count, if(transporttype=0,'Teleport',if(transporttype=1,'Walk', "
                 "'other')) from trs_stats_location_raw %s %s order by id asc" %
                 (str(query_date), (query_where), str(worker_where))
                 )

        res = self.execute(query)
        return res

    def statistics_get_location_info(self):
        logger.debug('Fetching all empty locations from db')
        query = (
            "select worker, sum(location_count), sum(location_ok), sum(location_nok), "
            "sum(location_nok) / sum(location_count) * 100 as Loc_fail_rate "
            "from trs_stats_location "
            "group by worker"
        )

        res = self.execute(query)
        return res

    def cleanup_statistics(self):
        logger.debug("Cleanup statistics tables")
        query = (
            "delete from trs_stats_detect where timestamp_scan < (UNIX_TIMESTAMP() - 604800)"
        )
        self.execute(query, commit=True)

        # stop deleting shiny entries. For science, please (-:
        query = (
            "delete from trs_stats_detect_raw where timestamp_scan < (UNIX_TIMESTAMP() - 604800) AND is_shiny = 0"
        )
        self.execute(query, commit=True)

        query = (
            "delete from trs_stats_location where timestamp_scan < (UNIX_TIMESTAMP() - 604800)"
        )
        self.execute(query, commit=True)

        query = (
            "delete from trs_stats_location_raw where period < (UNIX_TIMESTAMP() - 604800)"
        )
        self.execute(query, commit=True)

    def submit_cells(self, origin: str, map_proto: dict):
        cells = []
        protocells = map_proto.get("cells", [])

        query = ("INSERT INTO trs_s2cells (id, level, center_latitude, center_longitude, updated) "
                 "VALUES (%s, %s, %s, %s, %s) ON DUPLICATE KEY UPDATE "
                 "updated=VALUES(updated)"
                 )

        for cell in protocells:
            cell_id = cell["id"]

            if cell_id < 0:
                cell_id = cell_id + 2 ** 64

            lat, lng, alt = S2Helper.get_position_from_cell(cell_id)

            cells.append((cell_id, 15, lat, lng, cell["current_timestamp"] / 1000))

        self.executemany(query, cells, commit=True)

    def get_cells_in_rectangle(self, neLat, neLon, swLat, swLon,
                               oNeLat=None, oNeLon=None, oSwLat=None, oSwLon=None, timestamp=None):
        query = (
            "SELECT id, level, center_latitude, center_longitude, updated "
            "FROM trs_s2cells "
        )

        query_where = (
            " WHERE (center_latitude >= {} AND center_longitude >= {} "
            " AND center_latitude <= {} AND center_longitude <= {}) "
        ).format(swLat, swLon, neLat, neLon)

        if oNeLat is not None and oNeLon is not None and oSwLat is not None and oSwLon is not None:
            oquery_where = (
                " AND NOT (center_latitude >= {} AND center_longitude >= {} "
                " AND center_latitude <= {} AND center_longitude <= {}) "
            ).format(oSwLat, oSwLon, oNeLat, oNeLon)

            query_where = query_where + oquery_where

        elif timestamp is not None:
            tsdt = datetime.utcfromtimestamp(int(timestamp)).strftime("%Y-%m-%d %H:%M:%S")
            oquery_where = " AND updated >= '{}' ".format(tsdt)

            query_where = query_where + oquery_where

        res = self.execute(query + query_where)

        cells = []
        for (id, level, center_latitude, center_longitude, updated) in res:
            cells.append({
                "id": id,
                "level": level,
                "center_latitude": center_latitude,
                "center_longitude": center_longitude,
                "updated": updated
            })

        return cells

    def statistics_get_shiny_stats_hour(self):
        logger.debug('Fetching shiny pokemon stats from db')
        query = (
            "SELECT hour(FROM_UNIXTIME(timestamp_scan)) as hour, type_id FROM trs_stats_detect_raw where "
            "is_shiny=1 group by type_id, hour ORDER BY hour ASC"
        )

        res = self.execute(query)

        return res

    def update_trs_status_to_idle(self, origin):
        query = "UPDATE trs_status SET routemanager = 'idle' WHERE origin = '" + origin + "'"
        logger.debug(query)
        self.execute(query, commit=True)

