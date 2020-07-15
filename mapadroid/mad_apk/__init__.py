from multiprocessing.managers import SyncManager  # noqa: F401
from .abstract_apk_storage import AbstractAPKStorage  # noqa: F401
from .apk_enums import *   # noqa: F401 F403
from .apk_storage_db import APKStorageDatabase  # noqa: F401
from .apk_storage_fs import APKStorageFilesystem  # noqa: F401
from .custom_types import *  # noqa: F401 F403
from .utils import *  # noqa: F401 F403
from .wizard import APKWizard, PackageImporter, InvalidFile, WizardError  # noqa: F401


class StorageSyncManager(SyncManager):
    pass


def get_storage_obj(application_args, dbc):
    manager: StorageSyncManager
    storage_obj: StorageSyncManager = None
    if application_args.apk_storage_interface == 'db':
        StorageSyncManager.register('APKStorageDatabase', APKStorageDatabase)
        manager = StorageSyncManager()
        manager.start()
        storage_obj = manager.APKStorageDatabase(dbc)
    else:
        StorageSyncManager.register('APKStorageFilesystem', APKStorageFilesystem)
        manager = StorageSyncManager()
        manager.start()
        storage_obj = manager.APKStorageFilesystem(application_args)
    return (manager, storage_obj)
