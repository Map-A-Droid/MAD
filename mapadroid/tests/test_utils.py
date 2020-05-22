import io
from typing import NoReturn
from mapadroid.db.DbFactory import DbFactory
from mapadroid.mad_apk import APK_Arch, APK_Type, get_storage_obj, PackageImporter
from mapadroid.tests.local_api import LocalAPI
from mapadroid.utils.walkerArgs import parseArgs


filepath_rgc = 'APK/RemoteGpsController.apk'
mimetype = 'application/vnd.android.package-archive'
args = parseArgs()


class get_storage(object):
    cleanup_tables = ['mad_apk_autosearch', 'mad_apks']
    db_wrapper = None
    db_pool_manager = None
    storage_elem = None
    storage_mgr = None
    db_wrapper, db_pool_manager = DbFactory.get_wrapper(args)

    def __enter__(self):
        self.db_wrapper, self.db_pool_manager = DbFactory.get_wrapper(args)
        args.sdb = False
        (self.storage_manager, self.storage_elem) = get_storage_obj(args, self.db_wrapper)
        self.db_purge()
        return self.storage_elem

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.storage_manager.shutdown()
        self.db_pool_manager.shutdown()

    def db_purge(self):
        for table in get_storage.cleanup_tables:
            self.db_wrapper.execute('DELETE FROM `%s`' % (table,), commit=True)


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
            try:
                uri = next(iter(res.json()))
                login_check = api.get(uri)
                auth = (login_check.json()['username'], login_check.json()['password'])
            except StopIteration:
                pass
        res = api.get('api/device', params=params)
        if res.status_code == 200:
            try:
                origin = next(iter(res.json().values()))
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
