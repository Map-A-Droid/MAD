from mapadroid.mad_apk import APKType, WizardError
from mapadroid.tests.mad_apk.base_storage import StorageBase, upload_package


class WizardTests(StorageBase):
    def test_mistmatched_type(self):
        with self.assertRaises(WizardError):
            upload_package(self.storage_elem, apk_type=APKType.pd)
