import io
from typing import NoReturn
from mapadroid.mad_apk import APK_Arch, APK_Type, PackageImporter
from mapadroid.tests.local_api import LocalAPI


filepath_rgc = 'APK/RemoteGpsController.apk'
mimetype = 'application/vnd.android.package-archive'


def get_connection_api():
    return LocalAPI(api_type='api')


def get_connection_mitm(api: LocalAPI = None):
    origin = None
    auth = None
    headers = {}
    if api:
        params = {'hide_resource': 1}
        res = api.get('api/auth', params=params)
        if res.status_code == 200:
            devices = res.json()
            try:
                uri = next(iter(res.json()))
                login_check = api.get(uri)
                auth = (login_check.json()['username'], login_check.json()['password'])
            except StopIteration:
                pass
    if origin is not None:
        headers['Origin'] = origin
    return LocalAPI(api_type='mitm', auth=auth, headers=headers)


def get_rgc_bytes() -> io.BytesIO:
    data = io.BytesIO()
    with open(filepath_rgc, 'rb') as fh:
        data.write(fh.read())
    return data


def upload_rgc(storage_elem, version: str = None) -> NoReturn:
    data = get_rgc_bytes()
    if version is None:
        PackageImporter(APK_Type.rgc, APK_Arch.noarch, storage_elem, data, mimetype)
    else:
        storage_elem.save_file(APK_Type.rgc, APK_Arch.noarch, version, mimetype, data)
