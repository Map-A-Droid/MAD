# Base class for a patch.  Handles the patch and basic error handling.
from abc import ABC, abstractmethod
from typing import Optional

from mapadroid.db import DbSchemaUpdater
from mapadroid.db.DbWrapper import DbWrapper
from sqlalchemy.sql import text
from sqlalchemy.ext.asyncio import AsyncSession


class PatchBase(object, ABC):
    """Basic handling of a patch

    This class is the base for any patch.  It will perform pre- and post-
    validation around the patch to validate that it was successful.  It will
    only be marked as completed if there were no issues during execution

    Attributes:
        name (str): Name of the patch.  Keep it concise as it will be displayed
            in the logger
        descr (str): Long description of the patch.  It is not displayed in the
            logger so be as verbose as you want
        completed (bool): If the patch was completed (pre-, execute, post-)
        issues (bool): If any issues arose during the patch execution
    """
    name: str = None
    descr: str = None
    completed: bool = False
    issues: bool = False

    def __init__(self, logger, db_wrapper, args):
        logger.info('Applying patch: {}', self.name)
        self._logger = logger
        self._db: DbWrapper = db_wrapper
        self._schema_updater: DbSchemaUpdater = self._db.schema_updater
        self._application_args = args
        self._session: Optional[AsyncSession] = None

    async def run(self):
        async with self._db as session, session:
            async with session.begin():
                self._session = session
                if self._pre_validation():
                    await self._execute()
                    if not self.issues and self._post_validation():
                        self.completed = True
                if not self.issues:
                    await session.commit()
                else:
                    await session.rollback()

    async def _run_raw_sql_query(self, raw_query: str):
        await self._session.execute(text(raw_query))

    @abstractmethod
    async def _execute(self):
        raise NotImplementedError('Patch not implemented')

    def _post_validation(self) -> bool:
        return True

    def _pre_validation(self) -> bool:
        return True
