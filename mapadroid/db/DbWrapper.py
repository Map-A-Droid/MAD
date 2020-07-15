import json
import re
import time
from datetime import datetime, timedelta, timezone
from functools import reduce
from typing import List, Optional
from mapadroid.db.DbSchemaUpdater import DbSchemaUpdater
from mapadroid.db.DbPogoProtoSubmit import DbPogoProtoSubmit
from mapadroid.db.DbSanityCheck import DbSanityCheck
from mapadroid.db.DbStatsReader import DbStatsReader
from mapadroid.db.DbStatsSubmit import DbStatsSubmit
from mapadroid.db.DbWebhookReader import DbWebhookReader
from mapadroid.geofence.geofenceHelper import GeofenceHelper
from mapadroid.utils.collections import Location
from mapadroid.utils.s2Helper import S2Helper
from mapadroid.utils.logging import get_logger, LoggerEnums


logger = get_logger(LoggerEnums.database)


class DbWrapper:
    def __init__(self, db_exec, args):
        self._db_exec = db_exec
        self.application_args = args
        self._event_id: int = 1

        self.sanity_check: DbSanityCheck = DbSanityCheck(db_exec)
        self.sanity_check.check_all()
        self.supports_apks = self.sanity_check.supports_apks

        self.schema_updater: DbSchemaUpdater = DbSchemaUpdater(db_exec, args.dbname)
        self.proto_submit: DbPogoProtoSubmit = DbPogoProtoSubmit(db_exec)
        self.stats_submit: DbStatsSubmit = DbStatsSubmit(db_exec, args)
        self.stats_reader: DbStatsReader = DbStatsReader(db_exec)
        self.webhook_reader: DbWebhookReader = DbWebhookReader(db_exec, self)
        try:
            self.get_instance_id()
        except Exception:
            self.instance_id = None
            logger.warning('Unable to get instance id from the database.  If this is a new instance and the DB is not '
                           'installed, this message is safe to ignore')

    def set_event_id(self, eventid: int):
        self._event_id = eventid


    def close(self, conn, cursor):
        return self._db_exec.close(conn, cursor)

    def execute(self, sql, args=None, commit=False, **kwargs):
        return self._db_exec.execute(sql, args, commit, **kwargs)

    def executemany(self, sql, args, commit=False, **kwargs):
        return self._db_exec.executemany(sql, args, commit, **kwargs)

    def autofetch_all(self, sql, args=(), **kwargs):
        """ Fetch all data and have it returned as a dictionary """
        return self._db_exec.autofetch_all(sql, args=args, **kwargs)

    def autofetch_value(self, sql, args=(), **kwargs):
        """ Fetch the first value from the first row """
        return self._db_exec.autofetch_value(sql, args=args, **kwargs)

    def autofetch_row(self, sql, args=(), **kwargs):
        """ Fetch the first row and have it return as a dictionary """
        return self._db_exec.autofetch_row(sql, args=args, **kwargs)

    def autofetch_column(self, sql, args=None, **kwargs):
        """ get one field for 0, 1, or more rows in a query and return the result in a list
        """
        return self._db_exec.autofetch_column(sql, args=args, **kwargs)

    def autoexec_delete(self, table, keyvals, literals=[], where_append=[], **kwargs):
        return self._db_exec.autoexec_delete(table, keyvals, literals=literals, where_append=where_append, **kwargs)

    def autoexec_insert(self, table, keyvals, literals=[], optype="INSERT", **kwargs):
        return self._db_exec.autoexec_insert(table, keyvals, literals=literals, optype=optype, **kwargs)

    def autoexec_update(self, table, set_keyvals, **kwargs):
        return self._db_exec.autoexec_update(table, set_keyvals, **kwargs)

    def __db_timestring_to_unix_timestamp(self, timestring):
        try:
            dt = datetime.strptime(timestring, '%Y-%m-%d %H:%M:%S.%f')
        except ValueError:
            dt = datetime.strptime(timestring, '%Y-%m-%d %H:%M:%S')
        unixtime = (dt - datetime(1970, 1, 1)).total_seconds()
        return unixtime

    def get_next_raid_hatches(self, delay_after_hatch, geofence_helper=None):
        """
        In order to build a priority queue, we need to be able to check for the next hatches of raid eggs
        The result may not be sorted by priority, to be done at a higher level!
        :return: unsorted list of next hatches within delay_after_hatch
        """
        logger.debug3("DbWrapper::get_next_raid_hatches called")
        db_time_to_check = datetime.utcfromtimestamp(
            time.time()).strftime("%Y-%m-%d %H:%M:%S")

        query = (
            "SELECT start, latitude, longitude "
            "FROM raid "
            "LEFT JOIN gym ON raid.gym_id = gym.gym_id WHERE raid.end > %s AND raid.pokemon_id IS NULL"
        )
        sql_args = (
            db_time_to_check,
        )

        res = self.execute(query, sql_args)
        data = []
        for (start, latitude, longitude) in res:
            if latitude is None or longitude is None:
                logger.warning("lat or lng is none")
                continue
            elif geofence_helper and not geofence_helper.is_coord_inside_include_geofence([latitude, longitude]):
                logger.debug3("Excluded hatch at {}, {} since the coordinate is not inside the given include fences",
                              latitude, longitude)
                continue
            timestamp = self.__db_timestring_to_unix_timestamp(str(start))
            data.append((timestamp + delay_after_hatch,
                         Location(latitude, longitude)))

        logger.debug4("Latest Q: {}", data)
        return data

    def set_scanned_location(self, lat, lng):
        """
        Update scannedlocation (in RM) of a given lat/lng
        """
        logger.debug3("DbWrapper::set_scanned_location called")
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
        sql_args = (cell_id, lat, lng, now, -1, -1, -1, -1, -1, -1, -1, -1)
        self.execute(query, sql_args, commit=True)

        return True

    def check_stop_quest(self, latitude, longitude):
        """
        Update scannedlocation (in RM) of a given lat/lng
        """
        logger.debug3("DbWrapper::check_stop_quest called")
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
            logger.debug3('Pokestop has already a quest with CURDATE()')
            return True
        else:
            logger.debug3('Pokestop has not a quest with CURDATE()')
            return False

    def gyms_from_db(self, geofence_helper):
        """
        Retrieve all the gyms valid within the area set by geofence_helper
        :return: numpy array with coords
        """
        logger.debug3("DbWrapper::gyms_from_db called")
        if geofence_helper is None:
            logger.error("No geofence_helper! Not fetching gyms.")
            return []

        logger.debug3("Filtering with rectangle")
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
        logger.debug3("Got {} coordinates in this rect (minLat, minLon, maxLat, maxLon): {}", len(list_of_coords),
                      rectangle)

        geofenced_coords = geofence_helper.get_geofenced_coordinates(
            list_of_coords)
        return geofenced_coords

    def update_encounters_from_db(self, geofence_helper, latest=0):
        """
        Retrieve all encountered ids inside the geofence.
        :return: the new value of latest and a dict like encounter_id: disappear_time
        """
        logger.debug3("DbWrapper::update_encounters_from_db called")
        if geofence_helper is None:
            logger.error("No geofence_helper! Not fetching encounters.")
            return 0, {}

        logger.debug3("Filtering with rectangle")
        rectangle = geofence_helper.get_polygon_from_fence()
        query = (
            "SELECT latitude, longitude, encounter_id, "
            "UNIX_TIMESTAMP(CONVERT_TZ(disappear_time + INTERVAL 1 HOUR, '+00:00', @@global.time_zone)), "
            "UNIX_TIMESTAMP(CONVERT_TZ(last_modified, '+00:00', @@global.time_zone)), "
            "UNIX_TIMESTAMP(last_modified)"
            "FROM pokemon "
            "WHERE "
            "latitude >= %s AND longitude >= %s AND "
            "latitude <= %s AND longitude <= %s AND "
            "cp IS NOT NULL AND "
            "disappear_time > UTC_TIMESTAMP() - INTERVAL 1 HOUR AND "
            "last_modified > FROM_UNIXTIME(%s) "
        )

        params = rectangle
        params = params + (latest,)
        res = self.execute(query, params)
        list_of_coords = []
        for (latitude, longitude, encounter_id, disappear_time, last_modified, gmt_last_modified) in res:
            list_of_coords.append(
                [latitude, longitude, encounter_id, disappear_time, last_modified])
            latest = max(latest, gmt_last_modified)

        encounter_id_coords = geofence_helper.get_geofenced_coordinates(
            list_of_coords)
        logger.debug3("Got {} encounter coordinates within this rect and age (minLat, minLon, maxLat, maxLon, "
                      "last_modified): {}", len(encounter_id_coords), params)
        encounter_id_infos = {}
        for (latitude, longitude, encounter_id, disappear_time, last_modified) in encounter_id_coords:
            encounter_id_infos[encounter_id] = disappear_time

        return latest, encounter_id_infos

    def stops_from_db(self, geofence_helper=None, fence=None):
        """
        Retrieve all the pokestops valid within the area set by geofence_helper
        :return: numpy array with coords
        """
        logger.debug3("DbWrapper::stops_from_db called")

        min_lat, min_lon, max_lat, max_lon = -90, -180, 90, 180
        query_where: str = ""
        if geofence_helper is not None:
            min_lat, min_lon, max_lat, max_lon = geofence_helper.get_polygon_from_fence()

        if fence is not None:
            query_where = " and ST_CONTAINS(ST_GEOMFROMTEXT( 'POLYGON(( {} ))'), " \
                          "POINT(pokestop.latitude, pokestop.longitude))".format(str(fence))

        query = (
            "SELECT latitude, longitude "
            "FROM pokestop "
            "WHERE (latitude >= {} AND longitude >= {} "
            "AND latitude <= {} AND longitude <= {}) "
        ).format(min_lat, min_lon, max_lat, max_lon)

        query = query + str(query_where)

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

    def quests_from_db(self, ne_lat=None, ne_lon=None, sw_lat=None, sw_lon=None, o_ne_lat=None, o_ne_lon=None,
                       o_sw_lat=None, o_sw_lon=None, timestamp=None, fence=None):
        """
        Retrieve all the pokestops valid within the area set by geofence_helper
        :return: numpy array with coords
        """
        logger.debug3("DbWrapper::quests_from_db called")
        questinfo = {}

        query = (
            "SELECT pokestop.pokestop_id, pokestop.latitude, pokestop.longitude, trs_quest.quest_type, "
            "trs_quest.quest_stardust, trs_quest.quest_pokemon_id, trs_quest.quest_pokemon_form_id, "
            "trs_quest.quest_pokemon_costume_id, trs_quest.quest_reward_type, "
            "trs_quest.quest_item_id, trs_quest.quest_item_amount, pokestop.name, pokestop.image, "
            "trs_quest.quest_target, trs_quest.quest_condition, trs_quest.quest_timestamp, "
            "trs_quest.quest_task, trs_quest.quest_reward, trs_quest.quest_template "
            "FROM pokestop INNER JOIN trs_quest ON pokestop.pokestop_id = trs_quest.GUID "
            "WHERE DATE(from_unixtime(trs_quest.quest_timestamp,'%Y-%m-%d')) = CURDATE() "
        )

        query_where = ""

        if ne_lat is not None and ne_lon is not None and sw_lat is not None and sw_lon is not None:
            oquery_where = (
                " AND (latitude >= {} AND longitude >= {} "
                " AND latitude <= {} AND longitude <= {}) "
            ).format(sw_lat, sw_lon, ne_lat, ne_lon)

            query_where = query_where + oquery_where

        if o_ne_lat is not None and o_ne_lon is not None and o_sw_lat is not None and o_sw_lon is not None:
            oquery_where = (
                " AND NOT (latitude >= {} AND longitude >= {} "
                " AND latitude <= {} AND longitude <= {}) "
            ).format(o_sw_lat, o_sw_lon, o_ne_lat, o_ne_lon)

            query_where = query_where + oquery_where
        elif timestamp is not None:
            oquery_where = " AND trs_quest.quest_timestamp >= {}".format(timestamp)
            query_where = query_where + oquery_where

        if fence is not None:
            query_where = query_where + " and ST_CONTAINS(ST_GEOMFROMTEXT( 'POLYGON(( {} ))'), " \
                                        "POINT(pokestop.latitude, pokestop.longitude))".format(str(fence))

        res = self.execute(query + query_where)

        for (pokestop_id, latitude, longitude, quest_type, quest_stardust, quest_pokemon_id,
             quest_pokemon_form_id, quest_pokemon_costume_id, quest_reward_type,
             quest_item_id, quest_item_amount, name, image, quest_target, quest_condition,
             quest_timestamp, quest_task, quest_reward, quest_template) in res:
            mon = "%03d" % quest_pokemon_id
            form_id = "%02d" % quest_pokemon_form_id
            costume_id = "%02d" % quest_pokemon_costume_id
            questinfo[pokestop_id] = ({
                'pokestop_id': pokestop_id, 'latitude': latitude, 'longitude': longitude,
                'quest_type': quest_type, 'quest_stardust': quest_stardust,
                'quest_pokemon_id': mon, 'quest_pokemon_form_id': form_id,
                'quest_pokemon_costume_id': costume_id,
                'quest_reward_type': quest_reward_type, 'quest_item_id': quest_item_id,
                'quest_item_amount': quest_item_amount, 'name': name, 'image': image,
                'quest_target': quest_target,
                'quest_condition': quest_condition, 'quest_timestamp': quest_timestamp,
                'task': quest_task, 'quest_reward': quest_reward, 'quest_template': quest_template})

        return questinfo

    def get_pokemon_spawns(self, hours):
        """
        Get Pokemon Spawns for dynamic rarity
        """
        logger.debug3('Fetching pokemon spawns from db')
        query_where = ''
        if hours:
            hours = datetime.utcnow() - timedelta(hours=hours)
            query_where = ' where disappear_time > \'%s\' ' % str(hours)

        query = "SELECT pokemon_id, count(pokemon_id) from pokemon %s group by pokemon_id" % str(query_where)

        res = self.execute(query)

        total = reduce(lambda x, y: x + y[1], res, 0)

        return {'pokemon': res, 'total': total}

    def get_to_be_encountered(self, geofence_helper, min_time_left_seconds,
                              eligible_mon_ids: Optional[List[int]]):
        if min_time_left_seconds is None or eligible_mon_ids is None:
            logger.warning(
                "DbWrapper::get_to_be_encountered: Not returning any encounters since no time left or "
                "eligible mon IDs specified. Make sure both settings are set in area options: "
                "min_time_left_seconds and mon_ids_iv ")
            return []
        logger.debug3("Getting mons to be encountered")
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

        sql_args = (
            int(min_time_left_seconds),
        )

        results = self.execute(query, sql_args, commit=False)

        next_to_encounter = []
        for latitude, longitude, encounter_id, spawnpoint_id, pokemon_id, _ in results:
            if pokemon_id not in eligible_mon_ids:
                continue
            elif latitude is None or longitude is None:
                logger.warning("lat or lng is none")
                continue
            elif geofence_helper and not geofence_helper.is_coord_inside_include_geofence(
                    [latitude, longitude]):
                logger.debug3("Excluded encounter at {}, {} since the coordinate is not inside the given include "
                              " fences", latitude, longitude)
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

    def stop_from_db_without_quests(self, geofence_helper):
        logger.debug3("DbWrapper::stop_from_db_without_quests called")

        min_lat, min_lon, max_lat, max_lon = geofence_helper.get_polygon_from_fence()

        query = (
            "SELECT pokestop.latitude, pokestop.longitude "
            "FROM pokestop "
            "LEFT JOIN trs_quest ON pokestop.pokestop_id = trs_quest.GUID "
            "WHERE (pokestop.latitude >= {} AND pokestop.longitude >= {} "
            "AND pokestop.latitude <= {} AND pokestop.longitude <= {}) "
            "AND (DATE(from_unixtime(trs_quest.quest_timestamp,'%Y-%m-%d')) <> CURDATE() "
            "OR trs_quest.GUID IS NULL)"
        ).format(min_lat, min_lon, max_lat, max_lon)

        res = self.execute(query)
        list_of_coords: List[Location] = []

        for (latitude, longitude) in res:
            list_of_coords.append(Location(latitude, longitude))

        if geofence_helper is not None:
            geofenced_coords = geofence_helper.get_geofenced_coordinates(list_of_coords)
            return geofenced_coords
        else:
            return list_of_coords

    def any_stops_unvisited(self, geofence_helper: GeofenceHelper, origin: str):
        logger.debug3("DbWrapper::any_stops_unvisited called")
        min_lat, min_lon, max_lat, max_lon = geofence_helper.get_polygon_from_fence()
        query = (
            "SELECT pokestop.latitude, pokestop.longitude "
            "FROM pokestop "
            "LEFT JOIN trs_visited ON (pokestop.pokestop_id = trs_visited.pokestop_id AND trs_visited.origin='{}') "
            "WHERE pokestop.latitude >= {} AND pokestop.longitude >= {} "
            "AND pokestop.latitude <= {} AND pokestop.longitude <= {} "
            "AND trs_visited.origin IS NULL LIMIT 1"
        ).format(origin, min_lat, min_lon, max_lat, max_lon)

        res = self.execute(query)
        unvisited: List[Location] = []
        if geofence_helper is not None:
            for (latitude, longitude) in res:
                unvisited.append(Location(latitude, longitude))

            geofenced_coords = geofence_helper.get_geofenced_coordinates(unvisited)
            return len(geofenced_coords) > 0
        else:
            return len(res) > 0

    def stops_from_db_unvisited(self, geofence_helper: GeofenceHelper, origin: str):
        logger.debug3("DbWrapper::stops_from_db_unvisited called")
        min_lat, min_lon, max_lat, max_lon = geofence_helper.get_polygon_from_fence()
        query = (
            "SELECT pokestop.latitude, pokestop.longitude "
            "FROM pokestop "
            "LEFT JOIN trs_visited ON (pokestop.pokestop_id = trs_visited.pokestop_id AND trs_visited.origin='{}') "
            "WHERE pokestop.latitude >= {} AND pokestop.longitude >= {} "
            "AND pokestop.latitude <= {} AND pokestop.longitude <= {} "
            "AND trs_visited.origin IS NULL"
        ).format(origin, min_lat, min_lon, max_lat, max_lon)

        res = self.execute(query)
        unvisited: List[Location] = []

        for (latitude, longitude) in res:
            unvisited.append(Location(latitude, longitude))

        if geofence_helper is not None:
            geofenced_coords = geofence_helper.get_geofenced_coordinates(unvisited)
            return geofenced_coords
        else:
            return unvisited

    def get_gyms_in_rectangle(self, ne_lat, ne_lon, sw_lat, sw_lon, o_ne_lat=None, o_ne_lon=None, o_sw_lat=None,
                              o_sw_lon=None, timestamp=None):
        """
        Basically just for MADmin map. This method returns gyms within a certain rectangle.
        It also handles a diff/old area to reduce returned data. Also checks for updated
        elements withing the rectangle via the timestamp.
        """
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
        ).format(sw_lat, sw_lon, ne_lat, ne_lon)

        # but don't fetch gyms from a known rectangle
        if o_ne_lat is not None and o_ne_lon is not None and o_sw_lat is not None and o_sw_lon is not None:
            oquery_where = (
                " AND NOT (latitude >= {} AND longitude >= {} "
                " AND latitude <= {} AND longitude <= {}) "
            ).format(o_sw_lat, o_sw_lon, o_ne_lat, o_ne_lon)

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

    def get_mons_in_rectangle(self, ne_lat, ne_lon, sw_lat, sw_lon, o_ne_lat=None, o_ne_lon=None, o_sw_lat=None,
                              o_sw_lon=None, timestamp=None):
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
        ).format(sw_lat, sw_lon, ne_lat, ne_lon)

        if o_ne_lat is not None and o_ne_lon is not None and o_sw_lat is not None and o_sw_lon is not None:
            oquery_where = (
                " AND NOT (latitude >= {} AND longitude >= {} "
                " AND latitude <= {} AND longitude <= {}) "
            ).format(o_sw_lat, o_sw_lon, o_ne_lat, o_ne_lon)

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

    def get_stops_in_rectangle(self, ne_lat, ne_lon, sw_lat, sw_lon, o_ne_lat=None, o_ne_lon=None, o_sw_lat=None,
                               o_sw_lon=None, timestamp=None):
        args = []
        conversions = ['ps.`last_modified`', 'ps.`lure_expiration`', 'ps.`last_updated`',
                       'ps.`incident_start`',
                       'ps.`incident_expiration`']
        # base query to fetch stops
        query = (
            "SELECT ps.`pokestop_id`, ps.`enabled`, ps.`latitude`, ps.`longitude`,\n"
            "%s,\n"
            "%s,\n"
            "%s,\n"
            "%s,\n"
            "%s,\n"
            "ps.`active_fort_modifier`, ps.`name`, ps.`image`, ps.`incident_grunt_type`\n"
            "FROM pokestop ps\n"
        )
        query_where = (
            "WHERE (ps.`latitude` >= %%s AND ps.`longitude` >= %%s "
            " AND ps.`latitude` <= %%s AND ps.`longitude` <= %%s) "
        )
        args += [sw_lat, sw_lon, ne_lat, ne_lon]
        if o_ne_lat is not None and o_ne_lon is not None and o_sw_lat is not None and o_sw_lon is not None:
            oquery_where = (
                " AND NOT (ps.`latitude` >= %%s AND ps.`longitude` >= %%s "
                " AND ps.`latitude` <= %%s AND ps.`longitude` <= %%s) "
            )
            args += [o_sw_lat, o_sw_lon, o_ne_lat, o_ne_lon]
            query_where = query_where + oquery_where
        elif timestamp is not None:
            tsdt = datetime.utcfromtimestamp(int(timestamp)).strftime("%Y-%m-%d %H:%M:%S")
            oquery_where = " AND ps.`last_updated` >= %%s "
            args += [tsdt]
            query_where = query_where + oquery_where
        conversion_txt = []
        for conversion in conversions:
            conversion_txt.append(adjust_tz_to_utc(conversion))
        sql = query + query_where
        pokestops = self.autofetch_all(sql % tuple(conversion_txt), args=tuple(args))
        quests = self.quests_from_db(
            ne_lat=ne_lat,
            ne_lon=ne_lon,
            sw_lat=sw_lat,
            sw_lon=sw_lon,
            o_ne_lat=o_ne_lat,
            o_ne_lon=o_ne_lon,
            o_sw_lat=o_sw_lat,
            o_sw_lon=o_sw_lon,
            timestamp=timestamp
        )
        for pokestop in pokestops:
            pokestop['has_quest'] = pokestop['pokestop_id'] in quests
        return pokestops

    def delete_stop(self, latitude: float, longitude: float):
        logger.debug3('Deleting stop from db')
        query = (
            "delete from pokestop where latitude=%s and longitude=%s"
        )
        del_vars = (latitude, longitude)
        self.execute(query, del_vars, commit=True)

    def flush_levelinfo(self, origin):
        query = "DELETE FROM trs_visited WHERE origin=%s"
        self.execute(query, (origin,), commit=True)

    def submit_pokestop_visited(self, origin, latitude, longitude):
        logger.debug3("Flag pokestop as visited...")
        query = "INSERT IGNORE INTO trs_visited SELECT pokestop_id,'{}' " \
                "FROM pokestop WHERE latitude={} AND longitude={}".format(origin, str(latitude),
                                                                          str(longitude))
        self.execute(query, commit=True)

    def get_detected_spawns(self, geofence_helper, include_event_id) -> List[Location]:
        logger.debug3("DbWrapper::get_detected_spawns called")

        min_lat, min_lon, max_lat, max_lon = geofence_helper.get_polygon_from_fence()
        event_ids: list = []
        # adding default spawns
        event_ids.append(1)

        if include_event_id is not None:
            event_ids.append(include_event_id)

        query = (
            "SELECT latitude, longitude "
            "FROM trs_spawn "
            "WHERE (latitude >= {} AND longitude >= {} "
            "AND latitude <= {} AND longitude <= {}) and "
            "eventid in ({})"
        ).format(min_lat, min_lon, max_lat, max_lon, str(', '.join(str(v) for v in event_ids)))

        list_of_coords: List[Location] = []
        logger.debug3("DbWrapper::get_detected_spawns executing select query")
        res = self.execute(query)
        logger.debug4("DbWrapper::get_detected_spawns result of query: {}", res)
        for (latitude, longitude) in res:
            list_of_coords.append(Location(latitude, longitude))

        if geofence_helper is not None:
            logger.debug3("DbWrapper::get_detected_spawns applying geofence")
            geofenced_coords = geofence_helper.get_geofenced_coordinates(
                list_of_coords)
            logger.debug4(geofenced_coords)
            return geofenced_coords
        else:
            logger.debug3("DbWrapper::get_detected_spawns converting to numpy")
            return list_of_coords

    def get_undetected_spawns(self, geofence_helper, include_event_id):
        logger.debug3("DbWrapper::get_undetected_spawns called")

        min_lat, min_lon, max_lat, max_lon = geofence_helper.get_polygon_from_fence()
        event_ids: list = []
        # adding default spawns
        event_ids.append(1)

        if include_event_id is not None:
            event_ids.append(int(include_event_id))

        query = (
            "SELECT latitude, longitude "
            "FROM trs_spawn "
            "WHERE (latitude >= {} AND longitude >= {} "
            "AND latitude <= {} AND longitude <= {}) and "
            "calc_endminsec is NULL and "
            "eventid in ({})"
        ).format(min_lat, min_lon, max_lat, max_lon, str(', '.join(str(v) for v in event_ids)))

        list_of_coords: List[Location] = []
        logger.debug3("DbWrapper::get_undetected_spawns executing select query")
        res = self.execute(query)
        logger.debug4("DbWrapper::get_undetected_spawns result of query: {}", res)
        for (latitude, longitude) in res:
            list_of_coords.append(Location(latitude, longitude))

        if geofence_helper is not None:
            logger.debug4("DbWrapper::get_undetected_spawns applying geofence")
            geofenced_coords = geofence_helper.get_geofenced_coordinates(
                list_of_coords)
            logger.debug4(geofenced_coords)
            return geofenced_coords
        else:
            logger.debug3("DbWrapper::get_undetected_spawns converting to numpy")
            return list_of_coords

    def delete_spawnpoints(self, spawnpoint_ids):
        logger.debug3("dbWrapper::delete_spawnpoints")
        if len(spawnpoint_ids) == 0:
            return True
        query = (
            "DELETE "
            "FROM trs_spawn "
            "WHERE spawnpoint in ({})".format(str(','.join(spawnpoint_ids)))
        )

        self.execute(query, commit=True)
        return True

    def delete_status_entry(self, deviceid):
        logger.debug3("dbWrapper::delete_status_entry")
        query = (
            "DELETE "
            "FROM trs_status "
            "WHERE device_id ={}".format(str(deviceid))
        )

        self.execute(query, commit=True)
        return True

    def convert_spawnpoints(self, spawnpoint_ids):
        logger.debug3("dbWrapper::convert_spawnpoints")
        query = (
            "UPDATE trs_spawn "
            "set eventid = 1 WHERE spawnpoint in ({})".format(str(','.join(spawnpoint_ids)))
        )

        self.execute(query, commit=True)
        return True

    def delete_spawnpoint(self, spawnpoint_id):
        logger.debug3("dbWrapper::delete_spawnpoints")
        query = (
            "DELETE "
            "FROM trs_spawn "
            "WHERE spawnpoint={}".format(str(spawnpoint_id))
        )

        self.execute(query, commit=True)
        return True

    def convert_spawnpoint(self, spawnpoint_id):
        logger.debug3("dbWrapper::convert_spawnpoints")
        query = (
            "UPDATE trs_spawn "
            "set eventid = 1 WHERE spawnpoint={}".format(str(spawnpoint_id))
        )

        self.execute(query, commit=True)
        return True

    def get_all_spawnpoints(self):
        logger.debug3("dbWrapper::get_all_spawnpoints")
        spawn = []
        query = (
            "SELECT spawnpoint "
            "FROM `trs_spawn`"
        )
        res = self.execute(query)

        for (spawnid, ) in res:
            spawn.append(spawnid)

        return spawn

    def download_spawns(self, ne_lat=None, ne_lon=None, sw_lat=None, sw_lon=None, o_ne_lat=None, o_ne_lon=None,
                        o_sw_lat=None, o_sw_lon=None, timestamp=None, fence=None, eventid=None, todayonly=False,
                        olderthanxdays=None):
        logger.debug3("dbWrapper::download_spawns")
        spawn = {}
        query_where = ""

        query = (
            "SELECT spawnpoint, latitude, longitude, calc_endminsec, "
            "spawndef, if(last_scanned is not Null,last_scanned, '1970-01-01 00:00:00'), "
            "first_detection, if(last_non_scanned is not Null,last_non_scanned, '1970-01-01 00:00:00'), "
            "trs_event.event_name, trs_event.id "
            "FROM `trs_spawn` inner join trs_event on trs_event.id = trs_spawn.eventid "
        )

        if ne_lat is not None:
            query_where = (
                " WHERE (latitude >= {} AND longitude >= {} "
                " AND latitude <= {} AND longitude <= {}) "
            ).format(sw_lat, sw_lon, ne_lat, ne_lon)

        if o_ne_lat is not None and o_ne_lon is not None and o_sw_lat is not None and o_sw_lon is not None:
            query_where += (
                " AND NOT (latitude >= {} AND longitude >= {} "
                " AND latitude <= {} AND longitude <= {}) "
            ).format(o_sw_lat, o_sw_lon, o_ne_lat, o_ne_lon)

        elif timestamp is not None:
            tsdt = datetime.utcfromtimestamp(int(timestamp)).strftime("%Y-%m-%d %H:%M:%S")

            query_where += (
                " AND last_scanned >= '{}' "
            ).format(tsdt)

        if fence is not None:
            query_where = " WHERE ST_CONTAINS(ST_GEOMFROMTEXT( 'POLYGON(( {} ))'), " \
                          "POINT(trs_spawn.latitude, trs_spawn.longitude))".format(str(fence))

        if eventid is not None:
            query_where += " AND eventid = {}".format(str(eventid))

        if todayonly:
            query_where += " AND (DATE(last_scanned) = DATE(NOW()) OR DATE(last_non_scanned) = DATE(NOW())) "

        if olderthanxdays is not None:
            query_where += " AND (DATE(IF(last_scanned IS NOT Null,last_scanned, '1970-01-01 00:00:00'))" \
                           " < DATE(NOW()) - INTERVAL {} DAY AND " \
                           "DATE(IF(last_non_scanned IS NOT Null,last_non_scanned, '1970-01-01 00:00:00')) " \
                           "< DATE(NOW()) - INTERVAL {} DAY)".format(str(olderthanxdays), str(olderthanxdays))

        query += query_where
        res = self.execute(query)

        for (spawnid, lat, lon, endtime, spawndef, last_scanned, first_detection, last_non_scanned, eventname,
             eventid) in res:
            spawn[spawnid] = {
                'id': spawnid,
                'lat': lat,
                'lon': lon,
                'endtime': endtime,
                'spawndef': spawndef,
                'lastscan': str(last_scanned),
                'lastnonscan': str(last_non_scanned),
                'first_detection': int(first_detection.timestamp()),
                'event': eventname,
                'eventid': eventid
            }

        return str(json.dumps(spawn))

    def retrieve_next_spawns(self, geofence_helper):
        """
        Retrieve the spawnpoints with their respective unixtimestamp that are due in the next 300 seconds
        Check for Event and select only normal and (if active) current Event Spawns
        :return:
        """

        logger.debug3("DbWrapper::retrieve_next_spawns called")

        current_time_of_day = datetime.now().replace(microsecond=0)
        min_lat, min_lon, max_lat, max_lon = geofence_helper.get_polygon_from_fence()

        query = (
            "SELECT latitude, longitude, spawndef, calc_endminsec "
            "FROM trs_spawn "
            "WHERE calc_endminsec IS NOT NULL "
            "AND (latitude >= {} AND longitude >= {} AND latitude <= {} AND longitude <= {}) "
            "AND eventid in (1, {})"
        ).format(min_lat, min_lon, max_lat, max_lon, self._event_id)

        res = self.execute(query)
        next_up = []
        current_time = time.time()
        for (latitude, longitude, spawndef, calc_endminsec) in res:
            if geofence_helper and not geofence_helper.is_coord_inside_include_geofence(
                    [latitude, longitude]):
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

            timestamp = time.mktime(temp_date.timetuple()) - spawn_duration_minutes * 60
            # check if we calculated a time in the past, if so, add an hour to it...
            timestamp = timestamp + 60 * 60 if timestamp < current_time else timestamp
            next_up.append((timestamp, Location(latitude, longitude)))
        return next_up

    def get_nearest_stops_from_position(self, geofence_helper, origin: str, lat, lon, limit: int = 20,
                                        ignore_spinned: bool = True, maxdistance: int = 1):
        """
        Retrieve the nearest stops from lat / lon (optional with limit)
        :return:
        """

        logger.debug3("DbWrapper::get_nearest_stops_from_position called")
        limitstr: str = ""
        ignore_spinnedstr: str = ""
        loopcount: int = 0
        getlocations: bool = False

        min_lat, min_lon, max_lat, max_lon = geofence_helper.get_polygon_from_fence()
        if limit > 0:
            limitstr = "limit {}".format(limit)

        if ignore_spinned:
            ignore_spinnedstr = "AND trs_visited.origin IS NULL"

        while not getlocations:

            loopcount += 1
            if loopcount >= 10:
                logger.error("Not getting any new stop - abort")
                return []

            query = (
                "SELECT latitude, longitude, SQRT("
                "POW(69.1 * (latitude - {}), 2) + "
                "POW(69.1 * ({} - longitude), 2)) AS distance "
                "FROM pokestop "
                "LEFT JOIN trs_visited ON (pokestop.pokestop_id = trs_visited.pokestop_id AND trs_visited.origin='{}') "
                "where SQRT(POW(69.1 * (latitude - {}), 2) + POW(69.1 * ({} - longitude), 2)) <= {} and "
                "(latitude >= {} AND longitude >= {} AND latitude <= {} AND longitude <= {}) "
                "{} ORDER BY distance {} "
            ).format(lat, lon, origin, lat, lon, maxdistance, min_lat, min_lon, max_lat, max_lon, ignore_spinnedstr,
                     limitstr)

            res = self.execute(query)

            # getting 0 new locations - more distance!
            if len(res) == 0 or len(res) < limit:
                logger.warning("No location found or getting not enough locations - need more distance")
                maxdistance += 2

            else:
                # getting new locations
                logger.info("Getting enough locations - checking the coords now")

                stops: List[Location] = []

                for (latitude, longitude, distance) in res:
                    stops.append(Location(latitude, longitude))

                if geofence_helper is not None:
                    geofenced_coords = geofence_helper.get_geofenced_coordinates(stops)
                    if len(geofenced_coords) == limit:
                        return geofenced_coords
                    logger.warning("The coords are out of the fence - increase distance")
                    if loopcount >= 5:
                        # setting middle of fence as new startposition
                        lat, lon = geofence_helper.get_middle_from_fence()
                    else:
                        maxdistance += 3
                else:
                    return stops

        logger.error("Not getting any new stop - abort")
        return []

    def save_last_walker_position(self, origin, lat, lng):
        logger.debug3("dbWrapper::save_last_walker_position")

        query = (
            "update settings_device set startcoords_of_walker='%s, %s' where instance_id=%s and name=%s"
        )
        insert_values = (
            lat, lng, self.instance_id, origin
        )
        self.execute(query, insert_values, commit=True)

    def insert_usage(self, instance, cpu, mem, garbage, timestamp):
        logger.debug3("dbWrapper::insert_usage")

        query = (
            "INSERT into trs_usage (instance, cpu, memory, garbage, timestamp) VALUES "
            "(%s, %s, %s, %s, %s)"
        )
        insert_values = (
            instance, cpu, mem, garbage, timestamp
        )
        self.execute(query, insert_values, commit=True)

        return

    def save_status(self, data):
        logger.debug3("dbWrapper::save_status")
        literals = ['currentPos', 'lastPos', 'lastProtoDateTime']
        data['instance_id'] = self.instance_id
        self.autoexec_insert('trs_status', data, literals=literals, optype='ON DUPLICATE')

    def save_last_reboot(self, dev_id):
        logger.debug3("dbWrapper::save_last_reboot")
        literals = ['lastPogoReboot', 'globalrebootcount']
        data = {
            'instance_id': self.instance_id,
            'device_id': dev_id,
            'lastPogoReboot': 'NOW()',
            'globalrebootcount': '(globalrebootcount+1)',
            'restartCounter': 0,
            'rebootCounter': 0
        }
        self.autoexec_insert('trs_status', data, literals=literals, optype='ON DUPLICATE')

    def save_last_restart(self, dev_id):
        logger.debug3("dbWrapper::save_last_restart")
        literals = ['lastPogoRestart', 'globalrestartcount']
        data = {
            'instance_id': self.instance_id,
            'device_id': dev_id,
            'lastPogoRestart': 'NOW()',
            'globalrestartcount': '(globalrestartcount+1)',
            'restartCounter': 0
        }
        self.autoexec_insert('trs_status', data, literals=literals, optype='ON DUPLICATE')

    def save_idle_status(self, dev_id, status):
        data = {
            'instance_id': self.instance_id,
            'device_id': dev_id,
            'idle': status
        }
        self.autoexec_insert('trs_status', data, optype='ON DUPLICATE')

    def download_status(self):
        logger.debug3("dbWrapper::download_status")
        sql = "SELECT `device_id`, `name`, `routePos`, `routeMax`, `area_id`, `rmname`, `mode`, `rebootCounter`,\n"\
              "`init`, `currentSleepTime`, `rebootingOption`, `restartCounter`, `globalrebootcount`,\n"\
              "`globalrestartcount`, `lastPogoRestart`, `lastProtoDateTime`, `currentPos`, `lastPos`,\n"\
              "`lastPogoReboot`\n"\
              "FROM `v_trs_status`\n"\
              "WHERE `instance_id` = %s"
        workers = self.autofetch_all(sql, args=(self.instance_id,))
        return workers

    def get_events(self, event_id=None):
        logger.debug3("dbWrapper::get_events")
        eventidstr: str = ""
        if event_id is not None:
            eventidstr = "where `id` = " + str(event_id)
        sql = "select `id`, `event_name`, `event_start`, `event_end`, `event_lure_duration`, " \
              "IF(`event_name`='DEFAULT',1,0) as locked "\
              "from trs_event " + eventidstr + " order by id asc"
        events = self.autofetch_all(sql)
        return events

    def save_event(self, event_name, event_start, event_end, event_lure_duration=30, event_id=None):
        logger.debug3("DbWrapper::save_event called")
        if event_id is None:
            query = (
                "INSERT INTO trs_event (event_name, event_start, event_end, event_lure_duration) "
                "VALUES (%s, %s, %s, %s) "
            )
            sql_args = (event_name, event_start, event_end, event_lure_duration)
        else:
            query = (
                "UPDATE trs_event set event_name=%s, event_start=%s, event_end=%s, event_lure_duration=%s "
                "where id=%s"
            )
            sql_args = (event_name, event_start, event_end, event_lure_duration, event_id)

        self.execute(query, sql_args, commit=True)
        return True

    def delete_event(self, event_id=None):
        logger.debug3("DbWrapper::delete_event called")
        if event_id is None:
            return False
        else:
            # delete event
            query = (
                "DELETE from trs_event where id=%s"
            )
            sql_args = (event_id)
            self.execute(query, sql_args, commit=True)

            # delete SP with eventid
            query = (
                "DELETE from trs_spawn where eventid=%s"
            )
            sql_args = (event_id)
            self.execute(query, sql_args, commit=True)
        return True

    def get_current_event(self):
        logger.debug3("DbWrapper::get_current_event called")
        sql = (
            "SELECT id, event_lure_duration "
            "FROM trs_event "
            "WHERE NOW() BETWEEN event_start AND event_end AND event_name <> 'DEFAULT'"
        )

        found = self._db_exec.execute(sql)

        if found and len(found) > 0 and found[0][0]:
            logger.info("Found an active Event with id {} (Lure Duration: {})", found[0][0], found[0][1])
            return found[0][0], found[0][1]
        else:
            logger.info("There is no active event - returning default value (1) (Lure Duration: 30)")
            return 1, 30

    def check_if_event_is_active(self, eventid):
        logger.debug3("DbWrapper::check_if_event_is_active called")
        if int(eventid) == 1:
            return False
        sql = "select * " \
              "from trs_event " \
              "where now() between `event_start` and `event_end` and `id`=%s"
        sql_args = (eventid)
        res = self.execute(sql, sql_args)
        number_of_rows = len(res)
        if number_of_rows > 0:
            return True
        else:
            return False

    def get_cells_in_rectangle(self, ne_lat, ne_lon, sw_lat, sw_lon,
                               o_ne_lat=None, o_ne_lon=None, o_sw_lat=None, o_sw_lon=None, timestamp=None):
        query = (
            "SELECT id, level, center_latitude, center_longitude, updated "
            "FROM trs_s2cells "
        )

        query_where = (
            " WHERE (center_latitude >= {} AND center_longitude >= {} "
            " AND center_latitude <= {} AND center_longitude <= {}) "
        ).format(sw_lat, sw_lon, ne_lat, ne_lon)

        if o_ne_lat is not None and o_ne_lon is not None and o_sw_lat is not None and o_sw_lon is not None:
            oquery_where = (
                " AND NOT (center_latitude >= {} AND center_longitude >= {} "
                " AND center_latitude <= {} AND center_longitude <= {}) "
            ).format(o_sw_lat, o_sw_lon, o_ne_lat, o_ne_lon)

            query_where = query_where + oquery_where

        elif timestamp is not None:
            tsdt = datetime.utcfromtimestamp(int(timestamp)).strftime("%Y-%m-%d %H:%M:%S")
            oquery_where = " AND updated >= '{}' ".format(tsdt)

            query_where = query_where + oquery_where

        res = self.execute(query + query_where)

        cells = []
        for (cell_id, level, center_latitude, center_longitude, updated) in res:
            cells.append({
                "cell_id": id,
                "level": level,
                "center_latitude": center_latitude,
                "center_longitude": center_longitude,
                "updated": updated
            })

        return cells

    def get_instance_id(self, instance_name=None):
        if instance_name is None:
            instance_name = self.application_args.status_name
        sql = "SELECT `instance_id` FROM `madmin_instance` WHERE `name` = %s"
        res = self._db_exec.autofetch_value(sql, args=(instance_name,), suppress_log=True)
        if res:
            self.instance_id = res
        else:
            instance_data = {
                'name': instance_name
            }
            res = self._db_exec.autoexec_insert('madmin_instance', instance_data)
            self.instance_id = res
        return self.instance_id

    def get_mad_version(self):
        return self.autofetch_value('SELECT val FROM versions where versions.key = %s', args=('mad_version'),
                                    suppress_log=True)

    def update_mad_version(self, version):
        update_data = {
            'key': 'mad_version',
            'val': version
        }
        return self.autoexec_insert('versions', update_data, optype="ON DUPLICATE")


def adjust_tz_to_utc(column: str, as_name: str = None) -> str:
    # I would like to use convert_tz but this may not be populated.  Use offsets instead
    is_dst = time.daylight and time.localtime().tm_isdst > 0
    utc_offset = - (time.altzone if is_dst else time.timezone)
    if not as_name:
        try:
            as_name = re.findall(r'(\w+)', column)[-1]
        except Exception:
            as_name = column
    return "UNIX_TIMESTAMP(%s) + %s AS '%s'" % (column, utc_offset, as_name)
