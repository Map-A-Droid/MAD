import json
import sys
import time
from datetime import datetime, timedelta, timezone
from typing import List, Optional
from functools import reduce

import mysql
from bitstring import BitArray

from utils.collections import Location, LocationWithVisits
from utils.logging import logger
from utils.s2Helper import S2Helper
from db.DbSanityCheck import DbSanityCheck
from db.DbSchemaUpdater import DbSchemaUpdater
from db.DbPogoProtoSubmit import DbPogoProtoSubmit
from db.DbStatsSubmit import DbStatsSubmit


class DbWrapper:
    def_spawn = 240

    def __init__(self, db_exec, args):
        self._db_exec = db_exec
        self.application_args = args

        self.sanity_check: DbSanityCheck = DbSanityCheck(db_exec)
        self.sanity_check.ensure_correct_sql_mode()

        self.schema_updater: DbSchemaUpdater = DbSchemaUpdater(db_exec, args.dbname)
        self.schema_updater.ensure_unversioned_tables_exist()
        self.schema_updater.ensure_unversioned_columns_exist()

        self.proto_submit: DbPogoProtoSubmit = DbPogoProtoSubmit(db_exec, args.lure_duration)
        self.stats_submit: DbStatsSubmit = DbStatsSubmit(db_exec)


    def close(self, conn, cursor):
        return self._db_exec.close(conn, cursor)

    def execute(self, sql, args=None, commit=False):
        return self._db_exec.execute(sql, args, commit)

    def executemany(self, sql, args, commit=False):
        return self._db_exec.executemany(sql, args, commit)


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
        logger.debug("DbWrapper::get_next_raid_hatches called")
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
            timestamp = self.__db_timestring_to_unix_timestamp(str(start))
            data.append((timestamp + delay_after_hatch,
                         Location(latitude, longitude)))

        logger.debug("Latest Q: {}", str(data))
        return data

    def set_scanned_location(self, lat, lng, capture_time):
        """
        Update scannedlocation (in RM) of a given lat/lng
        """
        logger.debug("DbWrapper::set_scanned_location called")
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

        return True

    def check_stop_quest(self, latitude, longitude):
        """
        Update scannedlocation (in RM) of a given lat/lng
        """
        logger.debug("DbWrapper::check_stop_quest called")
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

    def gyms_from_db(self, geofence_helper):
        """
        Retrieve all the gyms valid within the area set by geofence_helper
        :return: numpy array with coords
        """
        logger.debug("DbWrapper::gyms_from_db called")
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
        """
        Retrieve all encountered ids inside the geofence.
        :return: the new value of latest and a dict like encounter_id: disappear_time
        """
        logger.debug("DbWrapper::update_encounters_from_db called")
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
        """
        Retrieve all the pokestops valid within the area set by geofence_helper
        :return: numpy array with coords
        """
        logger.debug("DbWrapper::stops_from_db called")

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

    def quests_from_db(self, neLat=None, neLon=None, swLat=None, swLon=None, oNeLat=None, oNeLon=None,
                       oSwLat=None, oSwLon=None, timestamp=None, fence=None):
        """
        Retrieve all the pokestops valid within the area set by geofence_helper
        :return: numpy array with coords
        """
        logger.debug("DbWrapper::quests_from_db called")
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

        if fence is not None:
            query_where = query_where + " and ST_CONTAINS(ST_GEOMFROMTEXT( 'POLYGON(( {} ))'), " \
                                        "POINT(pokestop.latitude, pokestop.longitude))".format(str(fence))

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



    def get_pokemon_spawns(self, hours):
        """
        Get Pokemon Spawns for dynamic rarity
        """
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


    def get_to_be_encountered(self, geofence_helper, min_time_left_seconds, eligible_mon_ids: Optional[List[int]]):
        if min_time_left_seconds is None or eligible_mon_ids is None:
            logger.warning("DbWrapper::get_to_be_encountered: Not returning any encounters since no time left or "
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

    def stop_from_db_without_quests(self, geofence_helper, levelmode: bool = False):
        logger.debug("DbWrapper::stop_from_db_without_quests called")

        minLat, minLon, maxLat, maxLon = geofence_helper.get_polygon_from_fence()

        query = (
            "SELECT pokestop.latitude, pokestop.longitude, '' as visited_by "
            "FROM pokestop "
            "LEFT JOIN trs_quest ON pokestop.pokestop_id = trs_quest.GUID "
            "WHERE (pokestop.latitude >= {} AND pokestop.longitude >= {} "
            "AND pokestop.latitude <= {} AND pokestop.longitude <= {}) "
            "AND (DATE(from_unixtime(trs_quest.quest_timestamp,'%Y-%m-%d')) <> CURDATE() "
            "OR trs_quest.GUID IS NULL)"
        ).format(minLat, minLon, maxLat, maxLon)

        if levelmode:
            logger.info("Leveling mode, add info about visitation")
            query = (
                "SELECT pokestop.latitude, pokestop.longitude, GROUP_CONCAT(trs_visited.origin) as visited_by "
                "FROM pokestop "
                "LEFT JOIN trs_visited ON pokestop.pokestop_id = trs_visited.pokestop_id "
                "WHERE (pokestop.latitude >= {} AND pokestop.longitude >= {} "
                "AND pokestop.latitude <= {} AND pokestop.longitude <= {}) GROUP by pokestop.pokestop_id"
            ).format(minLat, minLon, maxLat, maxLon)

        res = self.execute(query)
        list_of_coords: List[Location] = []
        visited_by_workers: List[LocationWithVisits] = []

        for (latitude, longitude, visited_by) in res:
            list_of_coords.append(Location(latitude, longitude))
            visited_by_workers.append(LocationWithVisits(latitude, longitude, visited_by))

        if geofence_helper is not None:
            geofenced_coords = geofence_helper.get_geofenced_coordinates(
                list_of_coords)
            return geofenced_coords, visited_by_workers
        else:
            return list_of_coords, visited_by_workers

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

    def get_stops_changed_since(self, timestamp):
        query = (
            "SELECT pokestop_id, latitude, longitude, lure_expiration, name, image, active_fort_modifier, "
            "last_modified, last_updated, incident_start, incident_expiration, incident_grunt_type "
            "FROM pokestop "
            "WHERE last_updated >= %s AND (DATEDIFF(lure_expiration, '1970-01-01 00:00:00') > 0 OR "
            "incident_start IS NOT NULL)"
        )

        tsdt = datetime.utcfromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")
        res = self.execute(query, (tsdt, ))

        ret = []
        for (pokestop_id, latitude, longitude, lure_expiration, name, image, active_fort_modifier,
                last_modified, last_updated, incident_start, incident_expiration, incident_grunt_type) in res:

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
                "incident_expiration": int(incident_expiration.replace(tzinfo=timezone.utc).timestamp()) if incident_expiration is not None else None,
                "incident_grunt_type": incident_grunt_type
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
            "INNER JOIN trs_spawn ON pokemon.spawnpoint_id = trs_spawn.spawnpoint "
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

    def check_stop_quest_level(self, worker, latitude, longitude):
        logger.debug("DbWrapper::check_stop_quest_level called")
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

    def get_quests_changed_since(self, timestamp):
        pass

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

    def get_gyms_in_rectangle(self, neLat, neLon, swLat, swLon, oNeLat=None, oNeLon=None, oSwLat=None, oSwLon=None, timestamp=None):
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

    def get_stops_in_rectangle(self, neLat, neLon, swLat, swLon, oNeLat=None, oNeLon=None, oSwLat=None, oSwLon=None, timestamp=None):
        stops = {}

        # base query to fetch stops
        query = (
            "SELECT pokestop_id, enabled, latitude, longitude, last_modified, lure_expiration, "
            "active_fort_modifier, last_updated, name, image, incident_start, incident_expiration, "
            "incident_grunt_type "
            "FROM pokestop "
        )

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
            oquery_where = " AND last_updated >= '{}' ".format(tsdt)
            query_where = query_where + oquery_where

        res = self.execute(query + query_where)

        for (stop_id, enabled, latitude, longitude, last_modified, lure_expiration,
                active_fort_modifier, last_updated, name, image, incident_start,
                incident_expiration, incident_grunt_type) in res:

            stops[stop_id] = {
                "enabled": enabled,
                "latitude": latitude,
                "longitude": longitude,
                "last_modified": int(last_modified.replace(tzinfo=timezone.utc).timestamp()),
                "lure_expiration": int(lure_expiration.replace(tzinfo=timezone.utc).timestamp()) if lure_expiration is not None else None,
                "active_fort_modifier": active_fort_modifier,
                "last_updated": int(last_updated.replace(tzinfo=timezone.utc).timestamp()) if last_updated is not None else None,
                "name": name,
                "image": image,
                "incident_start": int(incident_start.replace(tzinfo=timezone.utc).timestamp()) if incident_start is not None else None,
                "incident_expiration": int(incident_expiration.replace(tzinfo=timezone.utc).timestamp()) if incident_expiration is not None else None,
                "incident_grunt_type": incident_grunt_type
            }

        return stops

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


    def statistics_get_shiny_stats(self):
        logger.debug('Fetching shiny pokemon stats from db')
        query = (
            "SELECT (select count(DISTINCT encounter_id) from pokemon inner join trs_stats_detect_raw on "
            "CAST(trs_stats_detect_raw.type_id as unsigned int)=pokemon.encounter_id where pokemon.pokemon_id=a.pokemon_id and "
            "trs_stats_detect_raw.worker=b.worker and pokemon.form=a.form), count(DISTINCT encounter_id), a.pokemon_id,"
            "b.worker, GROUP_CONCAT(DISTINCT encounter_id ORDER BY encounter_id DESC SEPARATOR '<br>'), a.form, b.timestamp_scan "
            "FROM pokemon a left join trs_stats_detect_raw b on a.encounter_id=CAST(b.type_id as unsigned int) where b.is_shiny=1 group by "
            "b.is_shiny, a.pokemon_id, a.form, b.worker order by b.timestamp_scan DESC "
        )

        res = self.execute(query)

        return res

    def statistics_get_shiny_stats_v2(self, timestamp_from: int, timestamp_to: int):
        logger.debug('Fetching shiny_stats_v2 pokemon stats from db')
        logger.debug('timestamp_from: {}', timestamp_from)
        logger.debug('timestamp_to: {}', timestamp_to)
        data = ()

        query = (
            "SELECT pokemon.pokemon_id, pokemon.form, pokemon.latitude, pokemon.longitude, pokemon.gender, pokemon.costume, "
            "tr.count, tr.timestamp_scan, tr.worker, pokemon.encounter_id FROM pokemon "
            "JOIN trs_stats_detect_raw tr on CAST(tr.type_id as unsigned int)=pokemon.encounter_id "
            "WHERE tr.is_shiny=1 "
        )

        if timestamp_from:
            logger.debug('timestamp_from set: {}', timestamp_from)
            query = query + "AND UNIX_TIMESTAMP(last_modified) > %s "
            data = data + (timestamp_from,)
        if timestamp_to:
            logger.debug('timestamp_to set: {}', timestamp_to)
            query = query + "AND UNIX_TIMESTAMP(last_modified) < %s "
            data = data + (timestamp_to,)
        query = query + " GROUP BY pokemon.encounter_id ORDER BY tr.timestamp_scan DESC"
        logger.debug('Final query: {}', query)
        logger.debug('data: {}', data)
        res = self.execute(query, data)
        return res

    def statistics_get_shiny_stats_global_v2(self, mon_id_list: set, timestamp_from: int, timestamp_to: int):
        logger.debug('Fetching shiny_stats_global_v2')
        data = ()

        query = (
                "SELECT count(*), pokemon_id, form, gender, costume FROM pokemon WHERE individual_attack IS NOT NULL "
        )
        query = query + "AND pokemon_id IN(" + ",".join(map(str, mon_id_list)) + ") "
        if timestamp_from:
            query = query + " AND UNIX_TIMESTAMP(last_modified) > %s "
            data = data + (timestamp_from,)
        if timestamp_to:
            query = query + " AND UNIX_TIMESTAMP(last_modified) < %s "
            data = data + (timestamp_to,)
        query = query + "GROUP BY pokemon_id, form"
        logger.debug('Final query for shiny_stats_global_v2: {}', query)
        res = self.execute(query, data)
        return res

    def delete_stop(self, latitude: float, longitude: float):
        logger.debug('Deleting stop from db')
        query = (
            "delete from pokestop where latitude=%s and longitude=%s"
        )
        del_vars = (latitude, longitude)
        self.execute(query, del_vars, commit=True)


    def flush_levelinfo(self, origin):
        query = "DELETE FROM trs_visited WHERE origin=%s"
        self.execute(query, (origin,), commit=True)

    def submit_pokestop_visited(self, origin, latitude, longitude):
        logger.debug("Flag pokestop as visited...")
        query = "INSERT IGNORE INTO trs_visited SELECT pokestop_id,'{}' " \
                "FROM pokestop WHERE latitude={} AND longitude={}".format(origin, str(latitude), str(longitude))
        self.execute(query, commit=True)


    def get_detected_spawns(self, geofence_helper) -> List[Location]:
        logger.debug("DbWrapper::get_detected_spawns called")

        minLat, minLon, maxLat, maxLon = geofence_helper.get_polygon_from_fence()

        query = (
            "SELECT latitude, longitude "
            "FROM trs_spawn "
            "WHERE (latitude >= {} AND longitude >= {} "
            "AND latitude <= {} AND longitude <= {}) "
        ).format(minLat, minLon, maxLat, maxLon)

        list_of_coords: List[Location] = []
        logger.debug(
            "DbWrapper::get_detected_spawns executing select query")
        res = self.execute(query)
        logger.debug(
            "DbWrapper::get_detected_spawns result of query: {}", str(res))
        for (latitude, longitude) in res:
            list_of_coords.append(Location(latitude, longitude))

        if geofence_helper is not None:
            logger.debug(
                "DbWrapper::get_detected_spawns applying geofence")
            geofenced_coords = geofence_helper.get_geofenced_coordinates(
                list_of_coords)
            logger.debug(geofenced_coords)
            return geofenced_coords
        else:
            logger.debug(
                "DbWrapper::get_detected_spawns converting to numpy")
            # to_return = np.zeros(shape=(len(list_of_coords), 2))
            # for i in range(len(to_return)):
            #     to_return[i][0] = list_of_coords[i][0]
            #     to_return[i][1] = list_of_coords[i][1]
            return list_of_coords

    def get_undetected_spawns(self, geofence_helper):
        logger.debug("DbWrapper::get_undetected_spawns called")

        query = (
            "SELECT latitude, longitude "
            "FROM trs_spawn "
            "WHERE calc_endminsec is NULL"
        )
        list_of_coords: List[Location] = []
        logger.debug(
            "DbWrapper::get_undetected_spawns executing select query")
        res = self.execute(query)
        logger.debug(
            "DbWrapper::get_undetected_spawns result of query: {}", str(res))
        for (latitude, longitude) in res:
            list_of_coords.append(Location(latitude, longitude))

        if geofence_helper is not None:
            logger.debug(
                "DbWrapper::get_undetected_spawns applying geofence")
            geofenced_coords = geofence_helper.get_geofenced_coordinates(
                list_of_coords)
            logger.debug(geofenced_coords)
            return geofenced_coords
        else:
            logger.debug(
                "DbWrapper::get_undetected_spawns converting to numpy")
            # to_return = np.zeros(shape=(len(list_of_coords), 2))
            # for i in range(len(to_return)):
            #     to_return[i][0] = list_of_coords[i][0]
            #     to_return[i][1] = list_of_coords[i][1]
            return list_of_coords


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

        logger.debug("DbWrapper::retrieve_next_spawns called")

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

    def save_status(self, instance, data):
        logger.debug("dbWrapper::save_status")

        query = (
            "INSERT into trs_status (instance, origin, currentPos, lastPos, routePos, routeMax, "
            "routemanager, rebootCounter, lastProtoDateTime, "
            "init, rebootingOption, restartCounter, currentSleepTime) values "
            "(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
            "ON DUPLICATE KEY UPDATE currentPos=VALUES(currentPos), "
            "lastPos=VALUES(lastPos), routePos=VALUES(routePos), "
            "routeMax=VALUES(routeMax), routemanager=VALUES(routemanager), "
            "rebootCounter=VALUES(rebootCounter), lastProtoDateTime=IF(LENGTH(VALUES(lastProtoDateTime))=0, lastProtoDateTime, VALUES(lastProtoDateTime)), "
            "init=VALUES(init), rebootingOption=VALUES(rebootingOption), restartCounter=VALUES(restartCounter), "
            "currentSleepTime=VALUES(currentSleepTime)"
        )
        vals = (
            instance,
            data["Origin"], str(data["CurrentPos"]), str(
                data["LastPos"]), data["RoutePos"], data["RouteMax"],
            data["Routemanager"], data["RebootCounter"], data["LastProtoDateTime"],
            data["Init"], data["RebootingOption"], data["RestartCounter"], data["CurrentSleepTime"]
        )
        self.execute(query, vals, commit=True)
        return

    def save_last_reboot(self, instance, origin):
        logger.debug("dbWrapper::save_last_reboot")
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        query = (
            "insert into trs_status(instance, origin, lastPogoReboot, globalrebootcount) "
            "values (%s, %s, %s, %s) "
            "ON DUPLICATE KEY UPDATE lastPogoReboot=VALUES(lastPogoReboot), globalrebootcount=(globalrebootcount+1)"

        )

        vals = (
            instance, origin, now, 1
        )

        self.execute(query, vals, commit=True)
        return

    def save_last_restart(self, instance, origin):
        logger.debug("dbWrapper::save_last_restart")
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        query = (

            "insert into trs_status(instance, origin, lastPogoRestart, globalrestartcount) "
            "values (%s, %s, %s, %s) "
            "ON DUPLICATE KEY UPDATE lastPogoRestart=VALUES(lastPogoRestart), globalrestartcount=(globalrestartcount+1)"

        )

        vals = (
            instance, origin, now, 1
        )

        self.execute(query, vals, commit=True)
        return

    def download_status(self, instance):
        logger.debug("dbWrapper::download_status")
        workerstatus = []

        query = (
            "SELECT origin, currentPos, lastPos, routePos, routeMax, "
            "routemanager, rebootCounter, lastProtoDateTime, lastPogoRestart, "
            "init, rebootingOption, restartCounter, globalrebootcount, globalrestartcount, lastPogoReboot, "
            "currentSleepTime "
            "FROM trs_status "
            "WHERE instance = '{}'"
        ).format(instance)

        result = self.execute(query)
        for (origin, currentPos, lastPos, routePos, routeMax, routemanager_id,
                rebootCounter, lastProtoDateTime, lastPogoRestart, init, rebootingOption, restartCounter,
                globalrebootcount, globalrestartcount, lastPogoReboot, currentSleepTime) in result:
            status = {
                "origin": origin,
                "currentPos": currentPos,
                "lastPos": lastPos,
                "routePos": routePos,
                "routeMax": routeMax,
                "routemanager_id": routemanager_id,
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

        return workerstatus

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

    def update_trs_status_to_idle(self, instance, origin):
        query = "UPDATE trs_status SET routemanager = 'idle' WHERE origin = '" + origin + "'"
        logger.debug(query)
        self.execute(query, commit=True)
