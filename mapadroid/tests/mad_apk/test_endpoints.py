import os
from mapadroid.mad_apk import APK_Arch, APK_Type
from mapadroid.tests.apk_base import APKTestBase
from mapadroid.tests.test_utils import filepath_rgc, get_rgc_bytes


class EndpointTests(APKTestBase):
    def web_upload_rgc(self, method: str = 'octet'):
        response = None
        uri = '/api/mad_apk/{}/{}'.format(APK_Type.rgc.name, APK_Arch.noarch.name)
        with open(filepath_rgc, 'rb') as fh:
            filename = filepath_rgc.rsplit(os.sep, 1)[1]
            if method == 'octet':
                headers = {
                    'Content-Type': 'application/octet-stream',
                    'filename': filename
                }
                data = fh
                response = self.api.post(uri, data=data, headers=headers)
            else:
                files = {'file': (filename, fh)}
                response = self.api.post(uri, data={'filename': filename}, files=files)
        return response

    def test_upload(self):
        response = self.web_upload_rgc()
        self.assertTrue(response.status_code == 201)
        response = self.web_upload_rgc(method='form')
        self.assertTrue(response.status_code == 201)

    def test_valid_api_endpoints(self):
        response = self.api.get('/api/mad_apk')
        self.assertTrue(response.status_code == 200)
        data = response.json()
        self.assertTrue(APK_Type.pogo.name in data)
        self.assertFalse(APK_Arch.noarch.name in data[APK_Type.pogo.name])
        self.assertTrue(APK_Arch.armeabi_v7a.name in data[APK_Type.pogo.name])
        self.assertTrue(APK_Arch.arm64_v8a.name in data[APK_Type.pogo.name])
        self.assertTrue(APK_Type.rgc.name in data)
        self.assertTrue(APK_Arch.noarch.name in data[APK_Type.rgc.name])
        self.assertFalse(APK_Arch.armeabi_v7a.name in data[APK_Type.rgc.name])
        self.assertFalse(APK_Arch.arm64_v8a.name in data[APK_Type.rgc.name])
        self.assertTrue(APK_Type.pd.name in data)
        self.assertTrue(APK_Arch.noarch.name in data[APK_Type.pd.name])
        self.assertFalse(APK_Arch.armeabi_v7a.name in data[APK_Type.pd.name])
        self.assertFalse(APK_Arch.arm64_v8a.name in data[APK_Type.pd.name])
        response = self.api.get('/api/mad_apk/{}'.format(APK_Type.pogo.name))
        self.assertTrue(response.status_code == 200)
        data = response.json()
        self.assertFalse(APK_Arch.noarch.name in data)
        self.assertTrue(APK_Arch.armeabi_v7a.name in data)
        self.assertTrue(APK_Arch.arm64_v8a.name in data)
        response = self.api.get('/api/mad_apk/{}/{}'.format(APK_Type.pogo.name, APK_Arch.armeabi_v7a))
        self.assertTrue(response.status_code == 200)
        required_keys = set(['version', 'file_id', 'filename', 'mimetype', 'size', 'arch_disp', 'usage_disp'])
        self.assertTrue(response.status_code == 200)
        self.assertEqual(required_keys, response.json().keys())

    def test_valid_mitm_endpoints(self):
        self.api.delete('api/mad_apk/rgc/noarch')
        response = self.mitm.get('mad_apk/rgc', headers={'Origin': 'notanoriginplz'})
        self.assertTrue(response.status_code == 403)
        response = self.mitm.get('mad_apk/rgc/noarch')
        self.assertTrue(response.status_code == 404)
        self.web_upload_rgc()
        response = self.mitm.get('mad_apk/rgc/noarch')
        self.assertTrue(response.status_code == 200)
        self.assertTrue(str(response.content) is not None)

    def test_download(self):
        self.web_upload_rgc()
        rgc_size = get_rgc_bytes().getbuffer().nbytes
        response = self.mitm.get('mad_apk/rgc/noarch/download')
        self.assertTrue(len(response.content) == rgc_size)
        response = self.api.get('api/mad_apk/rgc/noarch/download')
        self.assertTrue(len(response.content) == rgc_size)
