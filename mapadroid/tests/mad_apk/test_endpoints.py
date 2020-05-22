import os
from mapadroid.mad_apk import APK_Arch, APK_Type
from mapadroid.tests.apk_base import APKTestBase
from mapadroid.tests.test_utils import filepath_rgc


class EndpointTests(APKTestBase):
    def test_upload(self):
        uri = '/api/mad_apk/{}/{}'.format(APK_Type.rgc.name, APK_Arch.noarch.name)
        with open(filepath_rgc, 'rb') as fh:
            filename = filepath_rgc.rsplit(os.sep, 1)[1]
            headers = {
                'Content-Type': 'application/octet-stream',
                'filename': filename
            }
            data = fh
            r = self.api.post(uri, data=data, headers=headers)
            fh.seek(0,0)
            self.assertTrue(r.status_code == 201)
            files = {'file': (filename, fh)}
            r = self.api.post(uri, data={'filename': filename}, files=files)
            self.assertTrue(r.status_code == 201)
