from mapadroid.mad_apk import APKType, WizardError
from mapadroid.tests.mad_apk.base_storage import StorageBase, upload_rgc


class WizardTests(StorageBase):
    def test_mistmatched_type(self):
        with self.assertRaises(WizardError):
            upload_rgc(self.storage_elem, apk_type=APKType.pd)
