from mapadroid.utils.apk_enums import *  # noqa: F401 F403
from mapadroid.utils.custom_types import *  # noqa: F401 F403

from ..utils.madGlobals import MadGlobals
from .abstract_apk_storage import AbstractAPKStorage  # noqa: F401
from .apk_storage_db import APKStorageDatabase  # noqa: F401
from .apk_storage_fs import APKStorageFilesystem  # noqa: F401
from .utils import *  # noqa: F401 F403
from .wizard import (APKWizard, InvalidFile, PackageImporter,  # noqa: F401
                     WizardError)


async def get_storage_obj(dbc):
    if MadGlobals.application_args.apk_storage_interface == 'db':
        storage_obj = APKStorageDatabase(dbc, MadGlobals.application_args.maddev_api_token)
    else:
        storage_obj = APKStorageFilesystem(MadGlobals.application_args)
    await storage_obj.setup()
    return storage_obj
