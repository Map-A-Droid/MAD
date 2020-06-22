# Base class for a patch.  Handles the patch and basic error handling.
from mapadroid.data_manager import DataManager
from mapadroid.db import DbSchemaUpdater
from mapadroid.db.DbWrapper import DbWrapper


class PatchBase(object):
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

    def __init__(self, logger, db_wrapper, data_manager, args):
        logger.info('Applying patch: {}', self.name)
        self._logger = logger
        self._db: DbWrapper = db_wrapper
        self._schema_updater: DbSchemaUpdater = self._db.schema_updater
        self._data_manager: DataManager = data_manager
        self._application_args = args
        if self._pre_validation():
            self._execute()
            if not self.issues and self._post_validation():
                self.completed = True

    def _execute(self):
        raise NotImplementedError('Patch not implemented')

    def _post_validation(self) -> bool:
        return True

    def _pre_validation(self) -> bool:
        return True
