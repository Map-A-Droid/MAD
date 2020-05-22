import os
from mapadroid.mad_apk import APK_Arch, APK_Type
from mapadroid.tests.apk_base import APKTestBase
from mapadroid.tests.test_utils import filepath_rgc, upload_rgc, get_storage, get_rgc_bytes


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
            fh.seek(0, 0)
            self.assertTrue(r.status_code == 201)
            files = {'file': (filename, fh)}
            r = self.api.post(uri, data={'filename': filename}, files=files)
            self.assertTrue(r.status_code == 201)

    def test_valid_api_endpoints(self):
        r = self.api.get('/api/mad_apk')
        self.assertTrue(r.status_code == 200)
        data = r.json()
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
        r = self.api.get('/api/mad_apk/{}'.format(APK_Type.pogo.name))
        self.assertTrue(r.status_code == 200)
        data = r.json()
        self.assertFalse(APK_Arch.noarch.name in data)
        self.assertTrue(APK_Arch.armeabi_v7a.name in data)
        self.assertTrue(APK_Arch.arm64_v8a.name in data)
        r = self.api.get('/api/mad_apk/{}/{}'.format(APK_Type.pogo.name, APK_Arch.armeabi_v7a))
        self.assertTrue(r.status_code == 200)
        required_keys = set(['version', 'file_id', 'filename', 'mimetype', 'size', 'arch_disp', 'usage_disp'])
        self.assertTrue(r.status_code == 200)
        self.assertEqual(required_keys, r.json().keys())

    def test_valid_mitm_endpoints(self):
        with get_storage() as storage_elem:
            storage_elem.delete_file(APK_Type.rgc, APK_Arch.noarch)
            r = self.mitm.get('mad_apk/rgc', headers={'Origin': 'notanoriginplz'})
            self.assertTrue(r.status_code == 403)
            upload_rgc(storage_elem)
            r = self.mitm.get('mad_apk/rgc/noarch')
            self.assertTrue(r.status_code == 200)
            self.assertTrue(str(r.content) is not None)

    def test_download(self):
        with get_storage() as storage_elem:
            storage_elem.delete_file(APK_Type.rgc, APK_Arch.noarch)
            rgc_size = get_rgc_bytes().getbuffer().nbytes
            upload_rgc(storage_elem)
            r = self.mitm.get('mad_apk/rgc/noarch/download')
            self.assertTrue(len(r.content) == rgc_size)
            r = self.api.get('api/mad_apk/rgc/noarch/download')
            self.assertTrue(len(r.content) == rgc_size)
