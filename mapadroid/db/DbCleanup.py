import asyncio
from asyncio import Task
from typing import Optional

from mapadroid.db.DbWrapper import DbWrapper
from mapadroid.db.helper.PokemonHelper import PokemonHelper
from mapadroid.utils.logging import get_logger, LoggerEnums
from mapadroid.utils.madGlobals import application_args

logger = get_logger(LoggerEnums.database_cleanup)


class DbCleanup(object):
    __db_wrapper: DbWrapper
    __cleanup_task: Optional[Task]

    def __init__(self, db_wrapper: DbWrapper):
        self.__db_wrapper = db_wrapper
        self.__cleanup_task = None

    async def start(self):
        if not self.__cleanup_task:
            logger.info("Starting DB cleanup routine")
            loop = asyncio.get_running_loop()
            self.__cleanup_task = loop.create_task(self._run_cleanup_routine())

    async def stop(self):
        if self.__cleanup_task:
            self.__cleanup_task.cancel()
            self.__cleanup_task = None

    async def _run_cleanup_routine(self):
        while True:
            async with self.__db_wrapper as session, session:
                if application_args.delete_mons_n_hours:
                    logger.info("Cleaning up mon records of mons disappeared more than {} hours ago.",
                                application_args.delete_mons_n_hours)
                    await PokemonHelper.delete_older_than_n_hours(session, application_args.delete_mons_n_hours)

                await session.commit()
            await asyncio.sleep(300)
