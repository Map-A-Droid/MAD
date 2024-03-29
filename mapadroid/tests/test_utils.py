import copy
import io
import json
import time
from typing import List, NoReturn

import mapadroid.tests.test_variables as global_variables
from mapadroid.db.DbFactory import DbFactory
from mapadroid.tests.local_api import LocalAPI
from mapadroid.utils.walkerArgs import parse_args

filepath_rgc = 'APK/RemoteGpsController.apk'
mimetype = 'application/vnd.android.package-archive'
args = parse_args()


class ResourceCreator():
    generated_uris: List[str] = []
    index: int = int(time.time())
    prefix: str = 'ResourceCreator'

    def __init__(self, api, prefix=prefix):
        self.api = api
        self.prefix = prefix
        self.generated_uris = []

    def remove_resources(self):
        if self.generated_uris:
            for uri in reversed(self.generated_uris):
                self.delete_resource(uri)

    def add_created_resource(self, uri):
        if uri not in self.generated_uris:
            self.generated_uris.append(uri)

    def create_resource(self, uri, payload, **kwargs):
        response = self.api.post(uri, json=payload, **kwargs)
        created_uri = response.headers['X-Uri']
        self.add_created_resource(created_uri)
        ResourceCreator.index += 1
        return response

    def delete_resource(self, uri):
        response = self.api.delete(uri)
        if response.status_code in [202, 404] and uri in self.generated_uris:
            self.generated_uris.remove(uri)
        return response

    def create_valid_resource(self, resource, **kwargs):
        uri, payload, headers, elem = self.get_valid_resource(resource, **kwargs)
        response = self.create_resource(uri, payload, headers=headers)
        elem['uri'] = response.headers['X-Uri']
        return (elem, response)

    def get_valid_resource(self, resource, **kwargs):
        resource_def = global_variables.DEFAULT_OBJECTS[resource]
        try:
            payload = kwargs['payload']
            del kwargs['payload']
        except:  # noqa: E722
            payload = kwargs.get('payload', copy.copy(resource_def['payload']))
        headers = kwargs.get('headers', {})
        elem = {
            'uri': None,
            'resources': {}
        }
        name_elem = None
        if resource == 'area':
            elem['resources']['geofence_included'] = self.create_valid_resource('geofence')[0]
            elem['resources']['routecalc'] = self.create_valid_resource('routecalc')[0]
            payload['geofence_included'] = elem['resources']['geofence_included']['uri']
            payload['routecalc'] = elem['resources']['routecalc']['uri']
            payload['name'] %= (self.prefix, ResourceCreator.index)
            try:
                headers['X-Mode']
            except:  # noqa: E722
                headers['X-Mode'] = 'raids_mitm'
        elif resource == 'auth':
            name_elem = 'username'
        elif resource == 'device':
            elem['resources']['walker'] = self.create_valid_resource('walker')[0]
            elem['resources']['pool'] = self.create_valid_resource('devicesetting')[0]
            payload['walker'] = elem['resources']['walker']['uri']
            payload['pool'] = elem['resources']['pool']['uri']
            payload['origin'] %= (self.prefix, ResourceCreator.index)
        elif resource == 'devicesetting':
            name_elem = 'devicepool'
        elif resource == 'geofence':
            name_elem = 'name'
        elif resource == 'monivlist':
            name_elem = 'monlist'
        elif resource == 'pogoauth':
            name_elem = 'username'
        elif resource == 'walker':
            elem['resources']['walkerarea'] = self.create_valid_resource('walkerarea')[0]
            payload['setup'] = [elem['resources']['walkerarea']['uri']]
            name_elem = 'walkername'
        elif resource == 'walkerarea':
            elem['resources']['area'] = self.create_valid_resource('area')[0]
            payload['walkerarea'] = elem['resources']['area']['uri']
        payload = self.recursive_update(payload, kwargs)
        if name_elem and '%s' in payload[name_elem]:
            payload[name_elem] %= (self.prefix, ResourceCreator.index)
        return (resource_def['uri'], payload, headers, elem)

    def recursive_update(self, payload, elems):
        for key, value in elems.items():
            if key == 'headers':
                continue
            elif type(value) == dict:
                payload[key] = self.recursive_update(payload, value)
            else:
                payload[key] = value
        return payload


class GetStorage(object):
    cleanup_tables = ['mad_apk_autosearch', 'mad_apks']
    db_wrapper = None
    db_pool_manager = None
    storage_elem = None
    db_wrapper, db_pool_manager = DbFactory.get_wrapper(args)

    def __init__(self, api):
        self.api = api

    def __enter__(self):
        self.db_wrapper, self.db_pool_manager = DbFactory.get_wrapper(args)
        args.apk_storage_interface = 'fs'
        # (self.storage_manager, self.storage_elem) = get_storage_obj(args, self.db_wrapper)
        self.db_purge()
        self.pogo_versions = {
            APKArch.armeabi_v7a: None,
            APKArch.arm64_v8a: None,
        }
        # determine supported pogo versions
        with open('configs/version_codes.json', 'rb') as fh:
            data = json.load(fh)
            for version in list(data.keys()):
                version_info = version.rsplit('_')
                if version_info[-1] == '32':
                    self.pogo_versions[APKArch.armeabi_v7a] = version_info[0]
                elif version_info[-1] == '64':
                    self.pogo_versions[APKArch.arm64_v8a] = version_info[0]
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        # self.storage_manager.shutdown()
        self.db_pool_manager.shutdown()

    def db_purge(self):
        self.storage_elem.delete_file(APKType.rgc, APKArch.noarch)
        self.storage_elem.delete_file(APKType.pd, APKArch.noarch)
        self.storage_elem.delete_file(APKType.pogo, APKArch.arm64_v8a)
        self.storage_elem.delete_file(APKType.pogo, APKArch.armeabi_v7a)
        for table in GetStorage.cleanup_tables:
            self.db_wrapper.execute('DELETE FROM `%s`' % (table,), commit=True)

    def upload_all(self):
        self.upload_pd(reload=False)
        self.upload_pogo(reload=False)
        self.upload_rgc(reload=False)
        self.api.get('/api/mad_apk/reload')

    def upload_pd(self, reload: bool = True):
        upload_package(self.storage_elem, version="0.1", apk_type=APKType.pd, apk_arch=APKArch.noarch)
        if reload:
            self.api.get('/api/mad_apk/reload')

    def upload_pogo(self, reload: bool = True):
        upload_package(self.storage_elem, version=self.pogo_versions[APKArch.arm64_v8a], apk_type=APKType.pogo,
                       apk_arch=APKArch.arm64_v8a)
        upload_package(self.storage_elem, version=self.pogo_versions[APKArch.armeabi_v7a], apk_type=APKType.pogo,
                       apk_arch=APKArch.armeabi_v7a)
        if reload:
            self.api.get('/api/mad_apk/reload')

    def upload_rgc(self, reload: bool = True):
        upload_package(self.storage_elem, version="0.1", apk_type=APKType.rgc, apk_arch=APKArch.noarch)
        if reload:
            self.api.get('/api/mad_apk/reload')


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


def upload_package(storage_elem, version: str = None, apk_type: APKType = APKType.rgc,
                   apk_arch: APKArch = APKArch.noarch) -> NoReturn:
    data = get_rgc_bytes()
    if version is None:
        PackageImporter(apk_type, apk_arch, storage_elem, data, mimetype)
    else:
        storage_elem.save_file(apk_type, apk_arch, version, mimetype, data)
