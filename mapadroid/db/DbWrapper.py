import re
import time
from typing import Dict, Optional

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from mapadroid.db.DbAccessor import DbAccessor
from mapadroid.db.DbPogoProtoSubmit import DbPogoProtoSubmit
from mapadroid.db.helper.MadminInstanceHelper import MadminInstanceHelper
from mapadroid.db.helper.SettingsAreaHelper import SettingsAreaHelper
from mapadroid.db.helper.SettingsAreaIdleHelper import SettingsAreaIdleHelper
from mapadroid.db.helper.SettingsAreaInitMitmHelper import \
    SettingsAreaInitMitmHelper
from mapadroid.db.helper.SettingsAreaIvMitm import SettingsAreaIvMitmHelper
from mapadroid.db.helper.SettingsAreaMonMitmHelper import \
    SettingsAreaMonMitmHelper
from mapadroid.db.helper.SettingsAreaPokestopHelper import \
    SettingsAreaPokestopHelper
from mapadroid.db.helper.SettingsAreaRaidsMitm import \
    SettingsAreaRaidsMitmHelper
from mapadroid.db.model import (MadminInstance, SettingsArea, SettingsAreaIdle,
                                SettingsAreaInitMitm, SettingsAreaIvMitm,
                                SettingsAreaMonMitm, SettingsAreaPokestop,
                                SettingsAreaRaidsMitm)
from mapadroid.db.PooledQueryExecutor import PooledQueryExecutor
from mapadroid.utils.logging import LoggerEnums, get_logger
from mapadroid.worker.WorkerType import WorkerType

logger = get_logger(LoggerEnums.database)


class DbWrapper:
    def __init__(self, db_exec: PooledQueryExecutor, args):
        self._db_exec: PooledQueryExecutor = db_exec
        self.application_args = args
        self._event_id: int = 1

        # TODO: Restore functionality...
        # self.sanity_check: DbSanityCheck = DbSanityCheck(db_exec)
        # self.sanity_check.check_all()
        # self.supports_apks = self.sanity_check.supports_apks

        self.proto_submit: DbPogoProtoSubmit = DbPogoProtoSubmit(db_exec, args)
        self.__instance_id: Optional[int] = None

    async def setup(self) -> None:
        await self.proto_submit.setup()
        try:
            async with self as session, session:
                await self.update_instance_id(session)
                await session.commit()
        except Exception:
            self.__instance_id = None
            logger.warning('Unable to get instance id from the database.  If this is a new instance and the DB is not '
                           'installed, this message is safe to ignore')

    def get_instance_id(self) -> Optional[int]:
        return self.__instance_id

    async def __aenter__(self) -> AsyncSession:
        # TODO: Start AsyncSession within a semaphore and return it, aexit needs to close the session
        db_accessor: DbAccessor = self._db_exec.get_db_accessor()
        return await db_accessor.__aenter__()

    async def __aexit__(self, type_, value, traceback):
        # TODO await self.close()
        db_accessor: DbAccessor = self._db_exec.get_db_accessor()
        await db_accessor.__aexit__(type_, value, traceback)

    def set_event_id(self, eventid: int):
        self._event_id = eventid

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
        areas.update(await SettingsAreaInitMitmHelper.get_all(session, self.__instance_id))
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
        elif area_base.mode == WorkerType.INIT.value:
            return await SettingsAreaInitMitmHelper.get(session, self.__instance_id, area_id)
        else:
            return None

    @staticmethod
    def create_area_instance(mode: WorkerType) -> Optional[SettingsArea]:
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
        elif mode == WorkerType.INIT:
            return SettingsAreaInitMitm()
        else:
            return None

    async def get_cache(self) -> Redis:
        cache: Redis = await self._db_exec.get_cache()
        return cache


def adjust_tz_to_utc(column: str, as_name: str = None) -> str:
    # I would like to use convert_tz but this may not be populated.  Use offsets instead
    is_dst = time.daylight and time.localtime().tm_isdst > 0
    _offset = - (time.altzone if is_dst else time.timezone)
    if not as_name:
        try:
            as_name = re.findall(r'(\w+)', column)[-1]
        except Exception:
            as_name = column
    return "UNIX_TIMESTAMP(%s) + %s AS '%s'" % (column, _offset, as_name)
