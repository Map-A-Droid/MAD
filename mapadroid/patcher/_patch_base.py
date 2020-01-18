# Base class for a patch.  Handles the patch and basic error handling.
from mapadroid.utils.data_manager import DataManager
from mapadroid.db import DbSchemaUpdater
from mapadroid.db.DbWrapper import DbWrapper

class PatchBase(object):
    name: str = None
    descr: str = None
    completed: bool = False
    issues: bool = False
    def __init__(self, logger, db_wrapper, data_manager, args):
        logger.info('Initializing patch {}', self.name)
        self._logger = logger
        self._db: DbWrapper = db_wrapper
        self._schema_updater: DbSchemaUpdater = self._db.schema_updater
        self._data_manager: DataManager = data_manager
        self._application_args = args
        if self._pre_validation():
            self._logger.info('Applying patch')
            self._execute()
            if not self.issues:
                if self._post_validation():
                    self.completed = True

    def _execute(self):
        raise RunTimeException('Patch not implemented')

    def _post_validation(self) -> bool:
        return True

    def _pre_validation(self) -> bool:
        return True
