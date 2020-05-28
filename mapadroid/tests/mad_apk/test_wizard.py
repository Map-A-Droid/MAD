from mapadroid.mad_apk import APK_Type, WizardError
from mapadroid.tests.mad_apk.base_storage import StorageBase, upload_rgc


class WizardTests(StorageBase):
    def testMismatchedType(self):
        with self.assertRaises(WizardError):
            upload_rgc(self.storage_elem, apk_type=APK_Type.pd)
