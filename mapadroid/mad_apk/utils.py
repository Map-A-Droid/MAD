import io
import zipfile
from distutils.version import LooseVersion
from typing import AsyncGenerator, Dict, List, Optional, Tuple, Union

import apkutils
from aiocache import cached
from apkutils.apkfile import BadZipFile, LargeZipFile
from bs4 import BeautifulSoup
from sqlalchemy.ext.asyncio import AsyncSession

from mapadroid.utils.apk_enums import APKArch, APKPackage, APKType
from mapadroid.utils.custom_types import MADapks, MADPackage, MADPackages
from mapadroid.utils.global_variables import BACKEND_SUPPORTED_VERSIONS
from mapadroid.utils.logging import LoggerEnums, get_logger

from ..utils.functions import get_version_codes
from ..utils.madGlobals import NoMaddevApiTokenError
from ..utils.RestHelper import RestApiResult, RestHelper
from .abstract_apk_storage import AbstractAPKStorage

logger = get_logger(LoggerEnums.package_mgr)


def convert_to_backend(req_type: str, req_arch: str) -> Tuple[Optional[APKType], Optional[APKArch]]:
    """ Converts front-end input into backend enums

    Args:
        req_type (str): User-input for APKType
        req_arch (str): User-input for APKArch

    Returns (tuple):
        Returns a tuple of (APKType, APKArch) enums
    """
    backend_type: Optional[APKType] = None
    backend_arch: Optional[APKArch] = None
    try:
        if req_type is not None:
            backend_type = lookup_apk_enum(req_type)
    except (TypeError, ValueError):
        raise ValueError('Invalid Type.  Valid types are {}'.format([e.name for e in APKPackage]))
    try:
        if req_arch is None:
            req_arch = APKArch.noarch
        backend_arch: APKArch = lookup_arch_enum(req_arch)
    except (TypeError, ValueError):
        raise ValueError('Invalid Architecture.  Valid types are {}'.format([e.name for e in APKArch]))
    return backend_type, backend_arch


async def get_apk_status(storage_obj: AbstractAPKStorage) -> MADapks:
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
                try:
                    package_info: Optional[Union[MADPackage, MADPackages]] = await lookup_package_info(storage_obj,
                                                                                                       package, arch)
                except ValueError:
                    package_info: Optional[Union[MADPackage, MADPackages]] = None
                if package_info is None:
                    package_info: Optional[Union[MADPackage, MADPackages]] = MADPackage(package, arch)
                data[package][arch] = package_info
        if package in [APKType.pd, APKType.rgc]:
            try:
                package_info: Optional[Union[MADPackage, MADPackages]] = await lookup_package_info(storage_obj, package,
                                                                                                   APKArch.noarch)
            except ValueError:
                package_info: Optional[Union[MADPackage, MADPackages]] = None
            if package_info is None:
                package_info: Optional[Union[MADPackage, MADPackages]] = MADPackage(package, APKArch.noarch)
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


def get_apk_info(downloaded_file: io.BytesIO) -> Tuple[Optional[str], Optional[str]]:
    package_version: Optional[str] = None
    package_name: Optional[str] = None
    try:
        apk = apkutils.APK.from_io(downloaded_file).parse_resource()
    except Exception as e:  # noqa: E722 B001
        logger.warning('Unable to parse APK file')
        logger.exception(e)
    else:
        manifest = apk.get_manifest()
        try:
            soup = BeautifulSoup(manifest, "lxml-xml")
            package_version, package_name = (soup.manifest.get("android:versionName"), soup.manifest['package'])
        except (TypeError, KeyError) as e:
            logger.debug("Invalid manifest file. Potentially a split package")
            logger.exception(e)
            with zipfile.ZipFile(downloaded_file) as zip_data:
                for item in zip_data.infolist():
                    try:
                        with zip_data.open(item, 'r') as fh:
                            apk = apkutils.APK.from_io(io.BytesIO(fh.read()))
                            manifest = apk.get_manifest()
                            try:
                                soup = BeautifulSoup(manifest, "lxml-xml")
                                package_version, package_name = (soup.manifest["android:versionName"],
                                                                 soup.manifest['package'])
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


def lookup_apk_enum(name: Union[str, int]) -> APKType:
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


def lookup_arch_enum(name: Union[int, str]) -> APKArch:
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


async def lookup_package_info(storage_obj: AbstractAPKStorage, package: APKType,
                              architecture: APKArch = None) -> Optional[Union[MADPackage, MADPackages]]:
    """ Retrieve the information about the package.  If no architecture is specified, it will return MAD_PACKAGES
        containing all relevant architectures

    Args:
        storage_obj (AbstractAPKStorage): Storage interface for lookup
        package (APKType): Package to lookup
        architecture (APKArch): Architecture of the package to lookup

    Returns:
        Package or Packages info
    """
    package_info: Optional[MADPackages] = None
    try:
        package_info = await storage_obj.get_current_package_info(package)
    except AttributeError:
        pass
    if package_info is None:
        raise ValueError("Unable to find package {}".format(package.value))
    if architecture is None:
        return package_info
    else:
        try:
            fileinfo = package_info[architecture]
            if package == APKType.pogo and not await supported_pogo_version(
                    architecture,
                    fileinfo.version,
                    storage_obj.token
            ):
                raise ValueError("Version is not supported anymore.")
            return fileinfo
        except KeyError:
            logger.warning("Unable to find package {} for arch {}".format(package.name, architecture.name))
            return None


async def stream_package(session: AsyncSession, storage_obj,
                         apk_type: APKType, architecture: APKArch) -> Optional[Tuple[AsyncGenerator, str, str, str]]:
    """ Stream the package to the user

    Args:
        session:
        storage_obj (AbstractAPKStorage): Storage interface for grabbing the package
        apk_type (APKType): Package to lookup
        architecture (APKArch): Architecture of the package to lookup

    Returns:
        Tuple consisting of generator to fetch the bytes of the apk, the mimetype and filetype
    """
    package_info: Union[MADPackage, MADPackages] = await lookup_package_info(storage_obj, apk_type, architecture)
    if not package_info:
        return None
    if isinstance(package_info, MADPackage):
        mimetype = package_info.mimetype
        filename = package_info.filename
        version = package_info.version
    else:
        package: MADPackage = package_info.get(architecture)
        mimetype = package.mimetype
        filename = package.filename
        version = package.version

    gen_func: AsyncGenerator = await storage_obj.get_async_generator(session, package_info, apk_type, architecture)
    return gen_func, mimetype, filename, version


async def supported_pogo_version(architecture: APKArch, version: str, token: Optional[str]) -> bool:
    """ Determine if the com.nianticlabs.pokemongo package is supported by MAD

    Args:
        token: maddev token to be used for querying supported versions
        architecture (APKArch): Architecture of the package to lookup
        version (str): Version of the pogo package
    """
    if architecture == APKArch.armeabi_v7a:
        bits = '32'
    else:
        bits = '64'
    # Use the MADdev endpoint for supported
    try:
        supported_versions: Dict[str, List[str]] = await get_backend_versions(token)
    except NoMaddevApiTokenError:
        logger.warning("Maddev API token is not set, assuming a supported version being used.")
        return True
    except ConnectionError:
        logger.warning("Error connecting to MADdev, assuming a supported version being used.")
        return True
    if version in supported_versions.get(bits, []):
        return True
    # If the version is not supported, check the local
    # file for supported versions
    supported_versions: Dict[str, List[str]] = await get_local_versions()
    try:
        return version in supported_versions[bits]
    except KeyError:
        return False


async def get_supported_pogo(architecture: APKArch, token: Optional[str]) -> Dict[APKArch, List[str]]:
    """ Gather all supported versions of MAD

    Args:
        token: maddev token to be used for querying supported versions
        architecture (APKArch): Architecture of the package to lookup
    """
    if architecture == APKArch.armeabi_v7a:
        bits = '32'
    else:
        bits = '64'
    supported_versions: Dict[str, List[str]] = await get_local_versions()
    if supported_versions:
        try:
            supported_versions[bits]
        except KeyError:
            pass
        else:
            logger.info(
                (
                    "Using local versions for support. If this is incorrect, please delete"
                    "configs/version_codes.json"
                )
            )
            return await translate_pogo_versions(supported_versions)
    # Use the MADdev endpoint for supported
    try:
        supported_versions: Dict[str, List[str]] = await get_backend_versions(token)
    except NoMaddevApiTokenError:
        logger.warning("Maddev API token is not set and no local version_codes.json defined.")
        raise
    except ConnectionError:
        logger.warning("Error connecting to MADdev!")
        raise
    return await translate_pogo_versions(supported_versions)


async def translate_pogo_versions(supported_versions: Dict[str, List[str]]) -> Dict[APKArch, List[str]]:
    """Translate and sort pogo versions

    :param supported_versions: MAD supported versions from the backend
    """
    processed = {}
    for arch_str, supported in supported_versions.items():
        if arch_str == "32":
            arch = APKArch.armeabi_v7a
        else:
            arch = APKArch.arm64_v8a
        # A hacky way to ensure the latest "text-based" version is highest
        processed[arch] = sorted(supported, reverse=True)
    return processed



async def get_local_versions() -> Dict[str, List[str]]:
    """Lookup the supported versions through the version_codes file
    :return: Supported versions
    :rtype: dict
    """
    supported = {
        "32": [],
        "64": [],
    }
    local_supported = await get_version_codes()
    for composite_ver in local_supported.keys():
        version, arch = composite_ver.split("_", 1)
        supported[arch].append(version)
    if any(supported["32"]) or any(supported["64"]):
        return supported
    return {}


@cached(ttl=10 * 60)
async def get_backend_versions(token: Optional[str]) -> Dict[str, List[str]]:
    """Lookup the supported backend versions

    The backend returns a JSON formatted string that contains arch with supported
    versions.

    .. code-block:: python

        {"32": ["0.241.1", "0.243.0"], "64": ["0.241.1", "0.243.0"]}


    :param str token: Token used for querying the MADdev backend

    :return: Currently supported versions from the backend
    :rtype: dict
    """
    if not token:
        msg = (
            "The API token has not been set in the config. Please update "
            "the configuration to include 'maddev_api_token' to "
            "utilize the wizard."
        )
        logger.warning(msg)
        raise NoMaddevApiTokenError(msg)
    headers = {
        "Authorization": "Bearer {}".format(token),
        "Accept": "application/json",
    }
    result: RestApiResult = await RestHelper.send_get(BACKEND_SUPPORTED_VERSIONS, headers=headers)
    if result.status_code == 200:
        if "error" in result.result_body:
            raise ValueError("An error was returned, {}".format(result.result_body["error"]))
        else:
            return result.result_body
    elif result.status_code == 403:
        raise ConnectionError("Invalid API token. Verify the correct token is in-use")
    else:
        msg = (
            "Invalid response recieved from MADdev\n"
            "Status Code: {}\n"
            "Body: {}"
        ).format(result.status_code, result.result_body)
        logger.error(msg)
        raise ConnectionError(msg)
