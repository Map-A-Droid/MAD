import io
import zipfile
from distutils.version import LooseVersion
from typing import Generator, Tuple, Union

import apkutils
import requests
from apksearch.search import HEADERS
from apkutils.apkfile import BadZipFile, LargeZipFile
from flask import Response, stream_with_context

from mapadroid.utils.functions import get_version_codes
from mapadroid.utils.global_variables import CHUNK_MAX_SIZE
from mapadroid.utils.logging import LoggerEnums, get_logger

from .abstract_apk_storage import AbstractAPKStorage
from .apk_enums import APKArch, APKPackage, APKType
from .custom_types import MADapks, MADPackage, MADPackages

logger = get_logger(LoggerEnums.package_mgr)


def convert_to_backend(req_type: str, req_arch: str) -> Tuple[APKType, APKArch]:
    """ Converts front-end input into backend enums

    Args:
        req_type (str): User-input for APKType
        req_arch (str): User-input for APKArch

    Returns (tuple):
        Returns a tuple of (APKType, APKArch) enums
    """
    backend_type: APKType = None
    backend_arch: APKArch = None
    try:
        if req_type is not None:
            backend_type = lookup_apk_enum(req_type)
    except (TypeError, ValueError):
        pass
    try:
        if req_arch is None:
            req_arch = APKArch.noarch
        backend_arch: APKArch = lookup_arch_enum(req_arch)
    except (TypeError, ValueError):
        pass
    return (backend_type, backend_arch)


def file_generator(db, storage_obj, package: APKType, architecture: APKArch) -> Union[Generator, Response]:
    """ Create a generator for retrieving the stored package

    Args:
        storage_obj (AbstractAPKStorage): Storage interface for saving
        package (APKType): Package to save
        architecture (APKArch): Architecture of the package to save
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


def generator_from_db(dbc, package: APKType, architecture: APKArch) -> Generator:
    """ Create a generator for retrieving the stored package from the database

    Args:
        dbc: database wrapper
        package (APKType): Package to save
        architecture (APKArch): Architecture of the package to save
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


def get_apk_status(storage_obj: AbstractAPKStorage) -> MADapks:
    """ Returns all required packages and their status

    Args:
        storage_obj (AbstractAPKStorage): Storage interface for saving

    Returns (MADapks):
        All required packages and their information.  If a package is not installed it will be populated by an empty
        package
    """
    data = MADapks()
    for package in APKType:
        data[package] = MADPackages()
        if package == APKType.pogo:
            for arch in [APKArch.armeabi_v7a, APKArch.arm64_v8a]:
                (package_info, status_code) = lookup_package_info(storage_obj, package, arch)
                if package_info is None:
                    package_info = MADPackage(package, arch)
                data[package][arch] = package_info
        if package in [APKType.pd, APKType.rgc]:
            (package_info, status_code) = lookup_package_info(storage_obj, package, APKArch.noarch)
            if package_info is None:
                package_info = MADPackage(package, APKArch.noarch)
            data[package][APKArch.noarch] = package_info
    return data


def generate_filename(package: APKType, architecture: APKArch, version: str, mimetype: str) -> str:
    """ Generates the packages friendly-name

    Args:
        package (APKType): Package to save
        architecture (APKArch): Architecture of the package to save
        mimetype (str): Mimetype of the package
        version (str): Version of the package
    """
    if mimetype == 'application/zip':
        ext = 'zip'
    else:
        ext = 'apk'
    friendlyname = getattr(APKPackage, package.name).value
    return '{}__{}__{}.{}'.format(friendlyname, version, architecture.name, ext)


def get_apk_info(downloaded_file: io.BytesIO) -> Tuple[str, str]:
    package_version: str = None
    package_name: str = None
    try:
        apk = apkutils.APK(downloaded_file)
    except:  # noqa: E722 B001
        logger.warning('Unable to parse APK file')
    else:
        manifest = apk.get_manifest()
        try:
            package_version, package_name = (manifest['@android:versionName'], manifest['@package'])
        except (TypeError, KeyError):
            logger.debug("Invalid manifest file. Potentially a split package")
            with zipfile.ZipFile(downloaded_file) as zip_data:
                for item in zip_data.infolist():
                    try:
                        with zip_data.open(item, 'r') as fh:
                            apk = apkutils.APK(io.BytesIO(fh.read()))
                            manifest = apk.get_manifest()
                            try:
                                package_version = manifest['@android:versionName']
                                package_name = manifest['@package']
                            except KeyError:
                                pass
                    except (BadZipFile, LargeZipFile):
                        continue
    return package_version, package_name


def is_newer_version(first_ver: str, second_ver: str) -> bool:
    """ Determines if the first version is newer than the second """
    try:
        return LooseVersion(first_ver) > LooseVersion(second_ver)
    except AttributeError:
        return True


def lookup_apk_enum(name: str) -> APKType:
    """ Determine the APKType enum for a given value

    Args:
        name (str): Name or id to lookup
    """
    try:
        if type(name) is int or name.isdigit():
            return APKType(int(name))
        else:
            return getattr(APKType, APKPackage(name).name)
    except (AttributeError, ValueError):
        if name == 'pogo':
            return APKType.pogo
        elif name == 'rgc':
            return APKType.rgc
        elif name in ['pogodroid', 'pd']:
            return APKType.pd
    except TypeError:
        pass
    raise ValueError('No defined lookup for %s' % (name,))


def lookup_arch_enum(name: str) -> APKArch:
    """ Determine the APKArch enum for a given value

    Args:
        name (str): Name or id to lookup
    """
    try:
        return APKArch(int(name))
    except (AttributeError, ValueError):
        if name == 'noarch':
            return APKArch.noarch
        elif name in ['armeabi-v7a', 'armeabi_v7a']:
            return APKArch.armeabi_v7a
        elif name in ['arm64-v8a', 'arm64_v8a']:
            return APKArch.arm64_v8a
    except TypeError:
        pass
    raise ValueError('No defined lookup for %s' % (name,))


def lookup_package_info(storage_obj: AbstractAPKStorage, package: APKType,
                        architecture: APKArch = None) -> Tuple[Union[MADPackage, MADPackages], int]:
    """ Retrieve the information about the package.  If no architecture is specified, it will return MAD_PACKAGES
        containing all relevant architectures

    Args:
        storage_obj (AbstractAPKStorage): Storage interface for lookup
        package (APKType): Package to lookup
        architecture (APKArch): Architecture of the package to loopup

    Returns:
        Tuple containing (Package or Packages info, status code)
    """
    package_info: MADPackages = None
    try:
        package_info = storage_obj.get_current_package_info(package)
    except AttributeError:
        pass
    if package_info is None:
        return (None, 404)
    if architecture is None:
        return (package_info, 200)
    else:
        try:
            status_code: int = 200
            fileinfo = package_info[architecture]
            if package == APKType.pogo and not supported_pogo_version(architecture, fileinfo.version):
                status_code = 410
            return (fileinfo, status_code)
        except KeyError:
            return (None, 404)


def parse_frontend(**kwargs) -> Union[Tuple[APKType, APKArch], Response]:
    """ Converts front-end input into backend enums

    Args:
        req_type (str): User-input for APKType
        req_arch (str): User-input for APKArch

    Returns (tuple):
        Returns a tuple of (APKType, APKArch) enums or a flask.Response stating what is invalid
    """
    apk_type_o = kwargs.get('apk_type', None)
    apk_arch_o = kwargs.get('apk_arch', None)
    package, architecture = convert_to_backend(apk_type_o, apk_arch_o)
    if apk_type_o is not None and package is None:
        resp_msg = 'Invalid Type.  Valid types are {}'.format([e.name for e in APKPackage])
        return Response(status=404, response=resp_msg)
    if architecture is None and apk_arch_o is not None:
        resp_msg = 'Invalid Architecture.  Valid types are {}'.format([e.name for e in APKArch])
        return Response(status=404, response=resp_msg)
    return (package, architecture)


def stream_package(db, storage_obj, package: APKType, architecture: APKArch) -> Response:
    """ Stream the package to the user

    Args:
        storage_obj (AbstractAPKStorage): Storage interface for grabbing the package
        package (APKType): Package to lookup
        architecture (APKArch): Architecture of the package to lookup
    """
    package_info: MADPackage = lookup_package_info(storage_obj, package, architecture)[0]
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


def supported_pogo_version(architecture: APKArch, version: str) -> bool:
    """ Determine if the com.nianticlabs.pokemongo package is supported by MAD

    Args:
        architecture (APKArch): Architecture of the package to lookup
        version (str): Version of the pogo package
    """
    valid: bool = False
    if architecture == APKArch.armeabi_v7a:
        bits = '32'
    else:
        bits = '64'
    composite_key = '%s_%s' % (version, bits,)
    valid = composite_key in get_version_codes(force_gh=False)
    if not valid:
        valid = composite_key in get_version_codes(force_gh=True)
    if not valid:
        logger.debug("PoGo [{}] is not supported", composite_key)
    return valid


def perform_http_download(url: str, retries: int = 3) -> requests.Response:
    attempt = 0
    while attempt < retries:
        try:
            logger.info("Starting download of {}", url)
            data = requests.get(url, allow_redirects=True, headers=HEADERS)
            data.raise_for_status()
            logger.info("Download completed for {}", url)
            return data
        except Exception as err:
            logger.warning("Unable to download PoGo. Retry {} of {}. {}", attempt, retries, err)
            attempt += 1
            continue
    return None
