from distutils.version import LooseVersion
from flask import Response, stream_with_context
import json
import requests
from typing import Tuple, Union, Generator
from .apk_enums import APK_Arch, APK_Type, APK_Package  # noqa: F401
from .abstract_apk_storage import AbstractAPKStorage
from .custom_types import MAD_APKS, MAD_Package, MAD_Packages
from mapadroid.utils.global_variables import CHUNK_MAX_SIZE, ADDRESSES_GITHUB
from mapadroid.utils.logging import logger


def convert_to_backend(req_type: str, req_arch: str) -> Tuple[APK_Type, APK_Arch]:
    backend_type: APK_Type = None
    backend_arch: APK_Arch = None
    try:
        if req_type is not None:
            backend_type = lookup_apk_enum(req_type)
    except (TypeError, ValueError):
        pass
    try:
        if req_arch is None:
            req_arch = APK_Arch.noarch
        backend_arch: APK_Arch = lookup_arch_enum(req_arch)
    except (TypeError, ValueError):
        pass
    return (backend_type, backend_arch)


def file_generator(db, storage_obj, apk_type: APK_Type, apk_arch: APK_Arch) -> Generator:
    package_info: Tuple[str, int] = lookup_package_info(storage_obj, apk_type, apk_arch)
    if package_info[1] == 404:
        return Response(status=404, response=package_info[0])
    file_info = package_info[0]
    if storage_obj.get_storage_type() == 'fs':
        gen_func = generator_from_filesystem(storage_obj.get_package_path(file_info.filename))
    else:
        gen_func = generator_from_db(db, apk_type, apk_arch)
    return gen_func


def generator_from_db(dbc, package: APK_Type, architecture: APK_Arch) -> Generator:
    filestore_id_sql = "SELECT `filestore_id` FROM `mad_apks` WHERE `usage` = %s AND `arch` = %s"
    filestore_id = dbc.autofetch_value(filestore_id_sql,
                                       args=(package.value, architecture.value,))
    sql = "SELECT `chunk_id` FROM `filestore_chunks` WHERE `filestore_id` = %s"
    data_sql = "SELECT `data` FROM `filestore_chunks` WHERE `chunk_id` = %s"
    chunk_ids = dbc.autofetch_column(sql, args=(filestore_id,))
    for chunk_id in chunk_ids:
        yield dbc.autofetch_value(data_sql, args=(chunk_id))


def generator_from_filesystem(full_path) -> Generator:
    with open(full_path, 'rb') as fh:
        while True:
            data = fh.read(CHUNK_MAX_SIZE)
            if not data:
                break
            yield data


def get_apk_status(storage_obj: AbstractAPKStorage) -> MAD_APKS:
    data = MAD_APKS()
    for package in APK_Type:
        data[package] = MAD_Packages()
        if package == APK_Type.pogo:
            for arch in [APK_Arch.armeabi_v7a, APK_Arch.arm64_v8a]:
                (package_info, status_code) = lookup_package_info(storage_obj, package, arch)
                if package_info is None:
                    package_info = MAD_Package(package, arch)
                data[package][arch] = package_info
        if package in [APK_Type.pd, APK_Type.rgc]:
            (package_info, status_code) = lookup_package_info(storage_obj, package, APK_Arch.noarch)
            if package_info is None:
                package_info = MAD_Package(package, APK_Arch.noarch)
            data[package][APK_Arch.noarch] = package_info
    return data


def generate_filename(package: APK_Type, architecture: APK_Arch, version: str, mimetype: str) -> str:
    if mimetype == 'application/zip':
        ext = 'zip'
    else:
        ext = 'apk'
    friendlyname = getattr(APK_Package, package.name).value
    return '{}__{}__{}.{}'.format(friendlyname, version, architecture.name, ext)


def is_newer_version(first_ver: str, second_ver: str) -> bool:
    """ Determines if the first version is newer than the second """
    try:
        return LooseVersion(first_ver) > LooseVersion(second_ver)
    except AttributeError:
        return True


def lookup_apk_enum(name: str) -> APK_Type:
    try:
        if type(name) is int or name.isdigit():
            return APK_Type(int(name))
        else:
            return getattr(APK_Type, APK_Package(name).name)
    except (AttributeError, ValueError):
        if name == 'pogo':
            return APK_Type.pogo
        elif name == 'rgc':
            return APK_Type.rgc
        elif name in ['pogodroid', 'pd']:
            return APK_Type.pd
    except TypeError:
        pass
    raise ValueError('No defined lookup for %s' % (name,))


def lookup_arch_enum(name: str) -> APK_Arch:
    try:
        return APK_Arch(int(name))
    except (AttributeError, ValueError):
        if name == 'noarch':
            return APK_Arch.noarch
        elif name in ['armeabi-v7a', 'armeabi_v7a']:
            return APK_Arch.armeabi_v7a
        elif name in ['arm64-v8a', 'arm64_v8a']:
            return APK_Arch.arm64_v8a
    except TypeError:
        pass
    raise ValueError('No defined lookup for %s' % (name,))


def lookup_package_info(storage_obj: AbstractAPKStorage, apk_type: APK_Type,
                        apk_arch: APK_Arch = None) -> Union[MAD_Package, MAD_Packages]:
    package_info: MAD_Packages = storage_obj.get_current_package_info(apk_type)
    if package_info is None:
        return (None, 404)
    if apk_arch is None:
        return (package_info, 200)
    else:
        try:
            status_code: int = 200
            fileinfo = package_info[apk_arch]
            if apk_type == APK_Type.pogo and not supported_pogo_version(apk_arch, fileinfo.version):
                status_code = 410
            return (fileinfo, status_code)
        except KeyError:
            return (None, 404)


def parse_frontend(**kwargs) -> Union[Tuple[APK_Type, APK_Arch], Response]:
    apk_type_o = kwargs.get('apk_type', None)
    apk_arch_o = kwargs.get('apk_arch', None)
    apk_type, apk_arch = convert_to_backend(apk_type_o, apk_arch_o)
    if apk_type_o is not None and apk_type is None:
        resp_msg = 'Invalid Type.  Valid types are {}'.format([e.name for e in APK_Package])
        return Response(status=404, response=resp_msg)
    if apk_arch is None and apk_arch_o is not None:
        resp_msg = 'Invalid Architecture.  Valid types are {}'.format([e.name for e in APK_Arch])
        return Response(status=404, response=resp_msg)
    return (apk_type, apk_arch)


def stream_package(db, storage_obj, apk_type: APK_Type, apk_arch: APK_Arch) -> Response:
    package_info: MAD_Package = lookup_package_info(storage_obj, apk_type, apk_arch)[0]
    gen_func: Generator = file_generator(db, storage_obj, apk_type, apk_arch)
    return Response(
        stream_with_context(gen_func),
        content_type=package_info.mimetype,
        headers={
            'Content-Disposition': f'attachment; filename=%s' % (package_info.filename)
        }
    )


def supported_pogo_version(apk_arch: APK_Arch, version: str) -> bool:
    valid: bool = False
    if apk_arch == APK_Arch.armeabi_v7a:
        bits = '32'
    else:
        bits = '64'
    try:
        with open('configs/addresses.json') as fh:
            address_object = json.load(fh)
            composite_key = '%s_%s' % (version, bits,)
            address_object[composite_key]
            valid = True
    except KeyError:
        try:
            requests.get(ADDRESSES_GITHUB).json()[composite_key]
            valid = True
        except KeyError:
            pass
    if not valid:
        logger.info('Current version of POGO [{}] is not supported', composite_key)
    return valid
