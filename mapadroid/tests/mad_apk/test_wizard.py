from mapadroid.mad_apk import APKType, WizardError, APKWizard, APKArch
from mapadroid.tests.mad_apk.base_storage import StorageBase, upload_package
from mapadroid.tests.test_utils import GetStorage, get_connection_api
from unittest.mock import MagicMock
from mapadroid.utils.gplay_connector import GPlayConnector

class WizardTests(StorageBase):
    def test_mistmatched_type(self):
        with self.assertRaises(WizardError):
            upload_package(self.storage_elem, apk_type=APKType.pd)

    def test_version_newer_avail(self):
        with GetStorage(get_connection_api()) as storage:
            wizard = APKWizard(storage.db_wrapper, storage.storage_manager)
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
            wizard.get_latest_version = MagicMock(return_value=latest_supported)
            storage.storage_manager.get_current_version = MagicMock(return_value="0.123.3")
            wizard.get_latest = MagicMock(return_value=autosearch_latest)
            GPlayConnector.get_latest_version = MagicMock(return_value=gplay_latest)
            wizard_latest = wizard.find_latest_pogo(APKArch.arm64_v8a)
            self.assertTrue(wizard_latest is not None)
            self.assertTrue(latest_supported[APKArch.arm64_v8a]["versionCode"] == wizard_latest["version_code"])
            self.assertTrue(latest_supported[APKArch.arm64_v8a]["version"] == wizard_latest["version"])

    def test_version_supported_but_not_gplay(self):
        with GetStorage(get_connection_api()) as storage:
            wizard = APKWizard(storage.db_wrapper, storage.storage_manager)
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
            wizard.get_latest_version = MagicMock(return_value=latest_supported)
            storage.storage_manager.get_current_version = MagicMock(return_value="0.123.3")
            wizard.get_latest = MagicMock(return_value=autosearch_latest)
            GPlayConnector.get_latest_version = MagicMock(return_value=gplay_latest)
            wizard_latest = wizard.find_latest_pogo(APKArch.arm64_v8a)
            self.assertTrue(wizard_latest is None)

    def test_version_newest_not_supported_but_older_supported(self):
        with GetStorage(get_connection_api()) as storage:
            wizard = APKWizard(storage.db_wrapper, storage.storage_manager)
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
            wizard.get_latest_version = MagicMock(return_value=latest_supported)
            storage.storage_manager.get_current_version = MagicMock(return_value="0.123.3")
            wizard.get_latest = MagicMock(return_value=autosearch_latest)
            GPlayConnector.get_latest_version = MagicMock(return_value=gplay_latest)
            wizard_latest = wizard.find_latest_pogo(APKArch.arm64_v8a)
            self.assertTrue(wizard_latest is not None)
            self.assertTrue(latest_supported[APKArch.arm64_v8a]["versionCode"] == wizard_latest["version_code"])
            self.assertTrue(latest_supported[APKArch.arm64_v8a]["version"] == wizard_latest["version"])