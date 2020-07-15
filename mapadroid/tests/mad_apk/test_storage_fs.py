import os
import shutil
from mapadroid.mad_apk import APKStorageFilesystem, APKType, APKArch, generate_filename
from mapadroid.tests.mad_apk.base_storage import StorageBase
from mapadroid.tests.test_utils import mimetype
from mapadroid.utils.walkerArgs import parse_args


args = parse_args()


class StorageFS(StorageBase):
    storage_path = args.temp_path + '/' + APKStorageFilesystem.config_apks
    storage_type = 'fs'

    def storage_cleanup(self):
        try:
            shutil.rmtree(os.getcwd() + '/' + StorageFS.storage_path)
        except FileNotFoundError:
            pass

    def storage_init(self):
        self.storage_cleanup()
        try:
            os.mkdir(args.temp_path)
        except FileExistsError:
            pass
        os.mkdir(StorageFS.storage_path)

    def test_status_check(self):
        super().status_check()

    def test_upload_check(self):
        super().upload_check()

    def test_download_check(self):
        super().download_check()

    def test_delete_check(self):
        super().delete_check()

    def test_package_upgrade_check(self):
        version: str = '0.1'
        super().package_upgrade_check(version)
        relative_path = StorageFS.storage_path + '/' + generate_filename(APKType.rgc,
                                                                         APKArch.noarch, version, mimetype)
        self.assertFalse(os.path.exists(relative_path))

    def test_version_check(self):
        super().version_check
