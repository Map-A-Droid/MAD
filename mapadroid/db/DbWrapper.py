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
from mapadroid.db.helper.MadminInstanceHelper import MadminInstanceHelper
from mapadroid.db.helper.SettingsAreaHelper import SettingsAreaHelper
from mapadroid.db.helper.SettingsAreaIdleHelper import SettingsAreaIdleHelper
from mapadroid.db.helper.SettingsAreaIvMitm import SettingsAreaIvMitmHelper
from mapadroid.db.helper.SettingsAreaMonMitmHelper import \
    SettingsAreaMonMitmHelper
from mapadroid.db.helper.SettingsAreaPokestopHelper import \
    SettingsAreaPokestopHelper
from mapadroid.db.helper.SettingsAreaRaidsMitm import \
    SettingsAreaRaidsMitmHelper
from mapadroid.db.model import SettingsArea, MadminInstance, SettingsAreaIdle, SettingsAreaIvMitm, SettingsAreaMonMitm, \
    SettingsAreaPokestop, SettingsAreaRaidsMitm
from mapadroid.utils.collections import Location
from mapadroid.utils.logging import LoggerEnums, get_logger
from mapadroid.worker.WorkerType import WorkerType

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
        self.__instance_id: Optional[int] = None
        try:
            self.update_instance_id(session)
        except Exception:
            self.__instance_id = None
            logger.warning('Unable to get instance id from the database.  If this is a new instance and the DB is not '
                           'installed, this message is safe to ignore')

    def get_instance_id(self) -> Optional[int]:
        return self.__instance_id

    async def __aenter__(self) -> AsyncSession:
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

    def save_status(self, data):
        logger.debug3("dbWrapper::save_status")
        literals = ['currentPos', 'lastPos', 'lastProtoDateTime']
        data['instance_id'] = self.__instance_id
        self.autoexec_insert('trs_status', data, literals=literals, optype='ON DUPLICATE')

    async def update_instance_id(self, session: AsyncSession, instance_name: Optional[str] = None) -> MadminInstance:
        if instance_name is None:
            instance_name = self.application_args.status_name
        instance: Optional[MadminInstance] = await MadminInstanceHelper.get_by_name(session, instance_name)
        if not instance:
            instance = MadminInstance()
            instance.name = instance_name
            # TODO: Fetch again as it's an autoincrement?
            instance = await session.merge(instance)
            await session.commit()
        self.__instance_id = instance.instance_id
        return instance

    async def get_all_areas(self, session: AsyncSession) -> Dict[int, SettingsArea]:
        areas: Dict[int, SettingsArea] = {}
        areas.update(await SettingsAreaIdleHelper.get_all(session, self.__instance_id))
        areas.update(await SettingsAreaIvMitmHelper.get_all(session, self.__instance_id))
        areas.update(await SettingsAreaMonMitmHelper.get_all(session, self.__instance_id))
        areas.update(await SettingsAreaPokestopHelper.get_all(session, self.__instance_id))
        areas.update(await SettingsAreaRaidsMitmHelper.get_all(session, self.__instance_id))
        return areas

    async def get_area(self, session: AsyncSession, area_id: int) -> Optional[SettingsArea]:
        """

        Args:
            area_id:
            session:

        Returns: the first matching area subclass-instance
        """
        area_base: Optional[SettingsArea] = await SettingsAreaHelper.get(session, self.__instance_id, area_id)
        if not area_base:
            return None
        elif area_base.mode == WorkerType.IDLE.value:
            return await SettingsAreaIdleHelper.get(session, self.__instance_id, area_id)
        elif area_base.mode == WorkerType.IV_MITM.value:
            return await SettingsAreaIvMitmHelper.get(session, self.__instance_id, area_id)
        elif area_base.mode == WorkerType.MON_MITM.value:
            return await SettingsAreaMonMitmHelper.get(session, self.__instance_id, area_id)
        elif area_base.mode == WorkerType.STOPS.value:
            return await SettingsAreaPokestopHelper.get(session, self.__instance_id, area_id)
        elif area_base.mode == WorkerType.RAID_MITM.value:
            return await SettingsAreaRaidsMitmHelper.get(session, self.__instance_id, area_id)
        else:
            return None

    def create_area_instance(self, mode: WorkerType) -> Optional[SettingsArea]:
        if mode == WorkerType.IDLE:
            return SettingsAreaIdle()
        elif mode == WorkerType.IV_MITM:
            return SettingsAreaIvMitm()
        elif mode == WorkerType.MON_MITM:
            return SettingsAreaMonMitm()
        elif mode == WorkerType.STOPS:
            return SettingsAreaPokestop()
        elif mode == WorkerType.RAID_MITM:
            return SettingsAreaRaidsMitm()
        else:
            return None


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
