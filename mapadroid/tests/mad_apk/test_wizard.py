from mapadroid.mad_apk import APKType, APKWizard, WizardError, APKArch
from mapadroid.mad_apk.wizard import InvalidDownload
from mapadroid.tests.mad_apk.base_storage import StorageBase, upload_package
from mapadroid.tests.test_utils import GetStorage, get_connection_api
from unittest.mock import MagicMock, patch
from mapadroid.utils.gplay_connector import GPlayConnector
import io


TEST_GPLAY_RESPONSE = io.BytesIO(b"Dummy File")


class WizardTests(StorageBase):

    @patch('mapadroid.mad_apk.wizard.supported_pogo_version')
    @patch('mapadroid.mad_apk.wizard.get_apk_info')
    def test_invalid_version_from_gplay(self, get_apk_info, supported_pogo_version):
        supported_pogo_version.return_value = True
        get_apk_info.return_value = ("0.123.3", "com.ignored")
        latest_gplay = {
            "version_code": 20200901,
            "version": "0.123.4"
        }
        autosearch_latest = {
            "version": "0.123.4",
            "url": 20201001
        }
        with GetStorage(get_connection_api()) as storage:
            package_downloader = APKWizard(storage.db_wrapper, storage.storage_manager)
            package_downloader.find_latest_pogo = MagicMock(return_value=latest_gplay)
            storage.storage_manager.get_current_version = MagicMock(return_value=None)
            package_downloader.get_latest = MagicMock(return_value=autosearch_latest)
            GPlayConnector.download = MagicMock(return_value=TEST_GPLAY_RESPONSE)
            with self.assertRaises(InvalidDownload):
                package_downloader.download_pogo(APKArch.arm64_v8a)

    @patch('mapadroid.mad_apk.wizard.get_apk_info')
    def test_valid_version_from_gplay(self, get_apk_info):
        latest_gplay = {
            "version_code": 20200901,
            "version": "0.123.4"
        }
        autosearch_latest = {
            "version": "0.123.4",
            "url": 20201001
        }
        get_apk_info_resp = ("0.123.4", "com.ignored")
        get_apk_info.return_value = get_apk_info_resp
        with GetStorage(get_connection_api()) as storage:
            package_downloader = APKWizard(storage.db_wrapper, storage.storage_manager)
            package_downloader.find_latest_pogo = MagicMock(return_value=latest_gplay)
            storage.storage_manager.get_current_version = MagicMock(return_value="0.123.3")
            package_downloader.get_latest = MagicMock(return_value=autosearch_latest)
            GPlayConnector.download = MagicMock(return_value=TEST_GPLAY_RESPONSE)
            package_downloader.download_pogo(APKArch.arm64_v8a)

    def test_mistmatched_type(self):
        with self.assertRaises(WizardError):
            upload_package(self.storage_elem, apk_type=APKType.pd)

    def test_version_newer_avail(self):
        with GetStorage(get_connection_api()) as storage:
            package_downloader = APKWizard(storage.db_wrapper, storage.storage_manager)
            gplay_latest = (20201001, "0.123.4")
            latest_supported = {
                APKArch.arm64_v8a: {
                    "versionCode": 20201001,
                    "version": "0.123.4"
                }
            }
            autosearch_latest = {
                "version": "0.123.4",
                "url": 20201001
            }
            package_downloader.get_latest_version = MagicMock(return_value=latest_supported)
            storage.storage_manager.get_current_version = MagicMock(return_value="0.123.3")
            package_downloader.get_latest = MagicMock(return_value=autosearch_latest)
            GPlayConnector.get_latest_version = MagicMock(return_value=gplay_latest)
            wizard_latest = package_downloader.find_latest_pogo(APKArch.arm64_v8a)
            self.assertTrue(wizard_latest is not None)
            self.assertTrue(latest_supported[APKArch.arm64_v8a]["versionCode"] == wizard_latest["version_code"])
            self.assertTrue(latest_supported[APKArch.arm64_v8a]["version"] == wizard_latest["version"])

    def test_version_supported_but_not_gplay(self):
        with GetStorage(get_connection_api()) as storage:
            package_downloader = APKWizard(storage.db_wrapper, storage.storage_manager)
            gplay_latest = (20200901, "0.123.3")
            latest_supported = {
                APKArch.arm64_v8a: {
                    "versionCode": 20201001,
                    "version": "0.123.4"
                }
            }
            autosearch_latest = {
                "version": "0.123.4",
                "url": 20201001
            }
            package_downloader.get_latest_version = MagicMock(return_value=latest_supported)
            storage.storage_manager.get_current_version = MagicMock(return_value="0.123.3")
            package_downloader.get_latest = MagicMock(return_value=autosearch_latest)
            GPlayConnector.get_latest_version = MagicMock(return_value=gplay_latest)
            wizard_latest = package_downloader.find_latest_pogo(APKArch.arm64_v8a)
            self.assertTrue(wizard_latest is None)

    def test_version_newest_not_supported_but_older_supported(self):
        with GetStorage(get_connection_api()) as storage:
            package_downloader = APKWizard(storage.db_wrapper, storage.storage_manager)
            gplay_latest = (20201001, "0.123.4")
            latest_supported = {
                APKArch.arm64_v8a: {
                    "versionCode": 20200901,
                    "version": "0.123.3"
                }
            }
            autosearch_latest = {
                "version": "0.123.4",
                "url": 20201001
            }
            package_downloader.get_latest_version = MagicMock(return_value=latest_supported)
            storage.storage_manager.get_current_version = MagicMock(return_value="0.123.3")
            package_downloader.get_latest = MagicMock(return_value=autosearch_latest)
            GPlayConnector.get_latest_version = MagicMock(return_value=gplay_latest)
            wizard_latest = package_downloader.find_latest_pogo(APKArch.arm64_v8a)
            self.assertTrue(wizard_latest is not None)
            self.assertTrue(latest_supported[APKArch.arm64_v8a]["versionCode"] == wizard_latest["version_code"])
            self.assertTrue(latest_supported[APKArch.arm64_v8a]["version"] == wizard_latest["version"])
