import json
import re
import time
from datetime import datetime, timedelta, timezone
from functools import reduce
from typing import Dict, List, Optional, Tuple

from sqlalchemy.ext.asyncio import AsyncSession

from mapadroid.db.DbAccessor import DbAccessor
from mapadroid.db.DbPogoProtoSubmit import DbPogoProtoSubmit
from mapadroid.db.DbSanityCheck import DbSanityCheck
from mapadroid.db.DbSchemaUpdater import DbSchemaUpdater
from mapadroid.db.DbStatsReader import DbStatsReader
from mapadroid.db.DbStatsSubmit import DbStatsSubmit
from mapadroid.db.DbWebhookReader import DbWebhookReader
from mapadroid.db.helper.SettingsAreaIdleHelper import SettingsAreaIdleHelper
from mapadroid.db.helper.SettingsAreaIvMitm import SettingsAreaIvMitmHelper
from mapadroid.db.helper.SettingsAreaMonMitmHelper import \
    SettingsAreaMonMitmHelper
from mapadroid.db.helper.SettingsAreaPokestopHelper import \
    SettingsAreaPokestopHelper
from mapadroid.db.helper.SettingsAreaRaidsMitm import \
    SettingsAreaRaidsMitmHelper
from mapadroid.db.model import SettingsArea
from mapadroid.utils.collections import Location
from mapadroid.utils.logging import LoggerEnums, get_logger

logger = get_logger(LoggerEnums.database)


class DbWrapper:
    def __init__(self, db_exec, args, cache):
        self._db_exec = db_exec
        self.application_args = args
        self._event_id: int = 1

        self.sanity_check: DbSanityCheck = DbSanityCheck(db_exec)
        self.sanity_check.check_all()
        self.supports_apks = self.sanity_check.supports_apks

        self.schema_updater: DbSchemaUpdater = DbSchemaUpdater(db_exec, args.dbname)
        self.proto_submit: DbPogoProtoSubmit = DbPogoProtoSubmit(db_exec, args, cache)
        self.stats_submit: DbStatsSubmit = DbStatsSubmit(db_exec, args)
        self.stats_reader: DbStatsReader = DbStatsReader(db_exec)
        self.webhook_reader: DbWebhookReader = DbWebhookReader(db_exec, self)
        try:
            self.get_instance_id()
        except Exception:
            self.instance_id = None
            logger.warning('Unable to get instance id from the database.  If this is a new instance and the DB is not '
                           'installed, this message is safe to ignore')

    async def __aenter__(self):
        # TODO: Start AsyncSession within a semaphore and return it, aexit needs to close the session
        return None

    async def __aexit__(self, type_, value, traceback):
        # TODO await self.close()
        pass

    def set_event_id(self, eventid: int):
        self._event_id = eventid

    def close(self, conn, cursor):
        return self._db_exec.close(conn, cursor)

    def execute(self, sql, args=None, commit=False, **kwargs):
        return self._db_exec.execute(sql, args, commit, **kwargs)

    def autofetch_all(self, sql, args=(), **kwargs):
        """ Fetch all data and have it returned as a dictionary """
        return self._db_exec.autofetch_all(sql, args=args, **kwargs)

    async def autofetch_value_async(self, sql, args=(), **kwargs):
        """ Fetch the first value from the first row using asyncio """
        return await self._db_exec.autofetch_value_async(sql, args=args, **kwargs)

    def autofetch_value(self, sql, args=(), **kwargs):
        """ Fetch the first value from the first row """
        return self._db_exec.autofetch_value(sql, args=args, **kwargs)

    async def autofetch_row_async(self, sql, args=(), **kwargs):
        """ Fetch the first row and have it return as a dictionary """
        return await self._db_exec.autofetch_row_async(sql, args=args, **kwargs)

    def autofetch_row(self, sql, args=(), **kwargs):
        """ Fetch the first row and have it return as a dictionary """
        return self._db_exec.autofetch_row(sql, args=args, **kwargs)

    def autofetch_column(self, sql, args=None, **kwargs):
        """ get one field for 0, 1, or more rows in a query and return the result in a list
        """
        return self._db_exec.autofetch_column(sql, args=args, **kwargs)

    def autoexec_delete(self, table, keyvals, literals=None, where_append=None, **kwargs):
        if where_append is None:
            where_append = []
        if literals is None:
            literals = []
        return self._db_exec.autoexec_delete(table, keyvals, literals=literals, where_append=where_append, **kwargs)

    def autoexec_insert(self, table, keyvals, literals=None, optype="INSERT", **kwargs):
        if literals is None:
            literals = []
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

    async def quests_from_db(self, session: AsyncSession, ne_lat=None, ne_lon=None, sw_lat=None, sw_lon=None,
                             o_ne_lat=None, o_ne_lon=None, o_sw_lat=None, o_sw_lon=None, timestamp=None, fence=None):
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
            "trs_quest.quest_task, trs_quest.quest_reward, trs_quest.quest_template, pokestop.is_ar_scan_eligible "
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

        res = await self._db_exec._db_accessor.execute(query + query_where)

        for (pokestop_id, latitude, longitude, quest_type, quest_stardust, quest_pokemon_id,
             quest_pokemon_form_id, quest_pokemon_costume_id, quest_reward_type,
             quest_item_id, quest_item_amount, name, image, quest_target, quest_condition,
             quest_timestamp, quest_task, quest_reward, quest_template, is_ar_scan_eligible) in res:
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
                'task': quest_task, 'quest_reward': quest_reward, 'quest_template': quest_template,
                'is_ar_scan_eligible': is_ar_scan_eligible
            })

        return questinfo

    def stop_from_db_without_quests(self, geofence_helper, latlng=True):
        logger.debug3("DbWrapper::stop_from_db_without_quests called")
        fields = "pokestop.latitude, pokestop.longitude"

        min_lat, min_lon, max_lat, max_lon = geofence_helper.get_polygon_from_fence()
        if not latlng:
            fields = "pokestop.pokestop_id"

        query = (
            "SELECT " + fields + " "
            "FROM pokestop "
            "LEFT JOIN trs_quest ON pokestop.pokestop_id = trs_quest.GUID "
            "WHERE (pokestop.latitude >= {} AND pokestop.longitude >= {} "
            "AND pokestop.latitude <= {} AND pokestop.longitude <= {}) "
            "AND (DATE(from_unixtime(trs_quest.quest_timestamp,'%Y-%m-%d')) <> CURDATE() "
            "OR trs_quest.GUID IS NULL)"
        ).format(min_lat, min_lon, max_lat, max_lon)

        res = self.execute(query)
        list_of_coords: List[Location] = []

        if not latlng:
            list_of_ids: List = []
            for stopid in res:
                list_of_ids.append(''.join(stopid))
            return list_of_ids

        for (latitude, longitude) in res:
            list_of_coords.append(Location(latitude, longitude))

        if geofence_helper is not None:
            geofenced_coords = geofence_helper.get_geofenced_coordinates(list_of_coords)
            return geofenced_coords
        else:
            return list_of_coords

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
            "raid.end, raid.pokemon_id, raid.form, raid.costume, "
            "raid.evolution, gym.last_scanned "
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
             level, spawn, start, end, mon_id, form, costume, evolution, last_scanned) in res:

            nowts = datetime.now(tz=timezone.utc).timestamp()

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
                    "level": level,
                    "costume": costume,
                    "evolution": evolution
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

    def save_status(self, data):
        logger.debug3("dbWrapper::save_status")
        literals = ['currentPos', 'lastPos', 'lastProtoDateTime']
        data['instance_id'] = self.instance_id
        self.autoexec_insert('trs_status', data, literals=literals, optype='ON DUPLICATE')

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
                "cell_id": cell_id,
                "level": level,
                "center_latitude": center_latitude,
                "center_longitude": center_longitude,
                "updated": updated
            })

        return cells

    def deprecated_get_instance_id(self, instance_name=None):
        # TODO: Use MadminInstanceHelper::get_by_name accordingly
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

    async def get_all_areas(self, session: AsyncSession) -> Dict[int, SettingsArea]:
        areas: Dict[int, SettingsArea] = {}
        areas.update(await SettingsAreaIdleHelper.get_all(session, self.instance_id))
        areas.update(await SettingsAreaIvMitmHelper.get_all(session, self.instance_id))
        areas.update(await SettingsAreaMonMitmHelper.get_all(session, self.instance_id))
        areas.update(await SettingsAreaPokestopHelper.get_all(session, self.instance_id))
        areas.update(await SettingsAreaRaidsMitmHelper.get_all(session, self.instance_id))
        return areas


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
