from mapadroid.tests.mad_apk.base_storage import StorageBase


class StorageDB(StorageBase):
    cleanup_tables = ['filestore_meta', 'filestore_chunks', 'mad_apk_autosearch', 'mad_apks']
    storage_type = 'db'

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
        sql = "SELECT COUNT(DISTINCT `filestore_id`) FROM `filestore_meta`"
        self.assertTrue(self.db_wrapper.autofetch_value(sql) == 1)

    def test_version_check(self):
        super().version_check()
