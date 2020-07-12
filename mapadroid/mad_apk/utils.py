from distutils.version import LooseVersion
from flask import Response, stream_with_context
import json
import requests
from typing import Tuple, Union, Generator
from .apk_enums import APK_Arch, APK_Type, APK_Package
from .abstract_apk_storage import AbstractAPKStorage
from .custom_types import MAD_APKS, MAD_Package, MAD_Packages
from mapadroid.utils.global_variables import CHUNK_MAX_SIZE, ADDRESSES_GITHUB
from mapadroid.utils.logging import get_logger, LoggerEnums


logger = get_logger(LoggerEnums.package_mgr)


def convert_to_backend(req_type: str, req_arch: str) -> Tuple[APK_Type, APK_Arch]:
    """ Converts front-end input into backend enums

    Args:
        req_type (str): User-input for APK_Type
        req_arch (str): User-input for APK_Arch

    Returns (tuple):
        Returns a tuple of (APK_Type, APK_Arch) enums
    """
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


def file_generator(db, storage_obj, package: APK_Type, architecture: APK_Arch) -> Union[Generator, Response]:
    """ Create a generator for retrieving the stored package

    Args:
        storage_obj (AbstractAPKStorage): Storage interface for saving
        package (APK_Type): Package to save
        architecture (APK_Arch): Architecture of the package to save
    Returns:
        Generator for retrieving the package
    """
    package_info: Tuple[str, int] = lookup_package_info(storage_obj, package, architecture)
    if package_info[1] == 404:
        return Response(status=404, response=package_info[0])
    file_info = package_info[0]
    if storage_obj.get_storage_type() == 'fs':
        gen_func = generator_from_filesystem(storage_obj.get_package_path(file_info.filename))
    else:
        gen_func = generator_from_db(db, package, architecture)
    return gen_func


def generator_from_db(dbc, package: APK_Type, architecture: APK_Arch) -> Generator:
    """ Create a generator for retrieving the stored package from the database

    Args:
        dbc: database wrapper
        package (APK_Type): Package to save
        architecture (APK_Arch): Architecture of the package to save
    Returns:
        Generator for retrieving the package
    """
    filestore_id_sql = "SELECT `filestore_id` FROM `mad_apks` WHERE `usage` = %s AND `arch` = %s"
    filestore_id = dbc.autofetch_value(filestore_id_sql,
                                       args=(package.value, architecture.value,))
    sql = "SELECT `chunk_id` FROM `filestore_chunks` WHERE `filestore_id` = %s"
    data_sql = "SELECT `data` FROM `filestore_chunks` WHERE `chunk_id` = %s"
    chunk_ids = dbc.autofetch_column(sql, args=(filestore_id,))
    for chunk_id in chunk_ids:
        yield dbc.autofetch_value(data_sql, args=(chunk_id))


def generator_from_filesystem(full_path) -> Generator:
    """ Create a generator for retrieving the stored package from the disk

    Args:
        full_path (str): path to the file to retrieve
    Returns:
        Generator for retrieving the package
    """
    with open(full_path, 'rb') as fh:
        while True:
            data = fh.read(CHUNK_MAX_SIZE)
            if not data:
                break
            yield data


def get_apk_status(storage_obj: AbstractAPKStorage) -> MAD_APKS:
    """ Returns all required packages and their status

    Args:
        storage_obj (AbstractAPKStorage): Storage interface for saving

    Returns (MAD_APKS):
        All required packages and their information.  If a package is not installed it will be populated by an empty
        package
    """
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
    """ Generates the packages friendly-name

    Args:
        package (APK_Type): Package to save
        architecture (APK_Arch): Architecture of the package to save
        mimetype (str): Mimetype of the package
        version (str): Version of the package
    """
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
    """ Determine the APK_Type enum for a given value

    Args:
        name (str): Name or id to lookup
    """
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
    """ Determine the APK_Arch enum for a given value

    Args:
        name (str): Name or id to lookup
    """
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


def lookup_package_info(storage_obj: AbstractAPKStorage, package: APK_Type,
                        architecture: APK_Arch = None) -> Tuple[Union[MAD_Package, MAD_Packages], int]:
    """ Retrieve the information about the package.  If no architecture is specified, it will return MAD_PACKAGES
        containing all relevant architectures

    Args:
        storage_obj (AbstractAPKStorage): Storage interface for lookup
        package (APK_Type): Package to lookup
        architecture (APK_Arch): Architecture of the package to loopup

    Returns:
        Tuple containing (Package or Packages info, status code)
    """
    package_info: MAD_Packages = storage_obj.get_current_package_info(package)
    if package_info is None:
        return (None, 404)
    if architecture is None:
        return (package_info, 200)
    else:
        try:
            status_code: int = 200
            fileinfo = package_info[architecture]
            if package == APK_Type.pogo and not supported_pogo_version(architecture, fileinfo.version):
                status_code = 410
            return (fileinfo, status_code)
        except KeyError:
            return (None, 404)


def parse_frontend(**kwargs) -> Union[Tuple[APK_Type, APK_Arch], Response]:
    """ Converts front-end input into backend enums

    Args:
        req_type (str): User-input for APK_Type
        req_arch (str): User-input for APK_Arch

    Returns (tuple):
        Returns a tuple of (APK_Type, APK_Arch) enums or a flask.Response stating what is invalid
    """
    apk_type_o = kwargs.get('apk_type', None)
    apk_arch_o = kwargs.get('apk_arch', None)
    package, architecture = convert_to_backend(apk_type_o, apk_arch_o)
    if apk_type_o is not None and package is None:
        resp_msg = 'Invalid Type.  Valid types are {}'.format([e.name for e in APK_Package])
        return Response(status=404, response=resp_msg)
    if architecture is None and apk_arch_o is not None:
        resp_msg = 'Invalid Architecture.  Valid types are {}'.format([e.name for e in APK_Arch])
        return Response(status=404, response=resp_msg)
    return (package, architecture)


def stream_package(db, storage_obj, package: APK_Type, architecture: APK_Arch) -> Response:
    """ Stream the package to the user

    Args:
        storage_obj (AbstractAPKStorage): Storage interface for grabbing the package
        package (APK_Type): Package to lookup
        architecture (APK_Arch): Architecture of the package to lookup
    """
    package_info: MAD_Package = lookup_package_info(storage_obj, package, architecture)[0]
    gen_func: Generator = file_generator(db, storage_obj, package, architecture)
    if isinstance(gen_func, Response):
        return gen_func
    return Response(
        stream_with_context(gen_func),
        content_type=package_info.mimetype,
        headers={
            'Content-Disposition': 'attachment; filename={}'.format(package_info.filename)
        }
    )


def supported_pogo_version(architecture: APK_Arch, version: str) -> bool:
    """ Determine if the com.nianticlabs.pokemongo package is supported by MAD

    Args:
        architecture (APK_Arch): Architecture of the package to lookup
        version (str): Version of the pogo package
    """
    valid: bool = False
    if architecture == APK_Arch.armeabi_v7a:
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
