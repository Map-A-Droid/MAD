import asyncio
import io
import zipfile
from threading import Thread
from typing import Dict, NoReturn, Optional, Tuple

import apkutils
import cachetools.func
import requests
import urllib3
from apksearch import generate_download_url, package_search_match
from apksearch.entities import PackageBase, PackageVariant
from apkutils.apkfile import BadZipFile, LargeZipFile

from mapadroid.utils import global_variables
from mapadroid.utils.functions import get_version_codes
from mapadroid.utils.logging import LoggerEnums, get_logger

from .abstract_apk_storage import AbstractAPKStorage
from .apk_enums import APKArch, APKPackage, APKType
from .utils import (get_apk_info, get_supported_pogo, lookup_arch_enum,
                    lookup_package_info, perform_http_download)

logger = get_logger(LoggerEnums.package_mgr)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
APK_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows; U; Windows NT 5.1; de; rv:1.9.2.3) Gecko/20100401 Firefox/3.6.3',
}
MAX_RETRIES: int = 3  # Number of attempts for downloading on failure


class WizardError(Exception):
    pass


class InvalidDownload(WizardError):
    pass


class InvalidFile(WizardError):
    pass


class SearchError(WizardError):
    pass


class FoundVaraint(WizardError):
    pass


class APKWizard(object):
    """ The wizard will allow for simplified APK management for the required packages

    Args:
        dbc: Database wrapper
        storage: Abstract storage element for interacting with storage medium

    Attributes:
        dbc: Database wrapper
        storage: Abstract storage element for interacting with storage medium
    """
    storage: AbstractAPKStorage

    def __init__(self, dbc, storage: AbstractAPKStorage, api_token: str):
        self.storage: AbstractAPKStorage = storage
        self.api_token = api_token
        self.dbc = dbc

    def apk_all_actions(self) -> NoReturn:
        "Search and download all required packages"
        self.apk_all_download()

    def apk_all_download(self) -> NoReturn:
        "Download all packages in a non-blocking fashion"
        Thread(target=self.apk_nonblocking_download).start()

    def apk_all_search(self) -> NoReturn:
        "Search for updates for any required package"
        try:
            self.find_latest_pogo(APKArch.armeabi_v7a)
            self.find_latest_pogo(APKArch.arm64_v8a)
        except SearchError:
            # The error has already been logged as a warning
            pass
        self.find_latest_rgc(APKArch.noarch)
        self.find_latest_pd(APKArch.noarch)

    def apk_download(self, package: APKType, architecture: APKArch) -> NoReturn:
        """Download a specific package

        Args:
            package (APKType): Package to download
            architecture (APKArch): Architecture of the package to download
        """
        if package == APKType.pogo:
            self.download_pogo(architecture)
        elif package == APKType.rgc:
            self.download_rgc(architecture)
        elif package == APKType.pd:
            self.download_pd(architecture)

    def apk_nonblocking_download(self) -> NoReturn:
        "Download all packages"
        for arch in APKArch:
            if arch == APKArch.noarch:
                continue
            try:
                self.download_pogo(arch)
            except InvalidDownload:
                pass
        if self.find_latest_rgc(APKArch.noarch):
            self.download_rgc(APKArch.noarch)
        if self.find_latest_pd(APKArch.noarch):
            self.download_pd(APKArch.noarch)

    def apk_search(self, package: APKType, architecture: APKArch) -> NoReturn:
        """ Search for a specific package

        Args:
            package (APKType): Package to search
            architecture (APKArch): Architecture of the package to search
        """
        if package == APKType.pogo:
            try:
                self.find_latest_pogo(architecture)
            except SearchError:
                # The error has already been logged as a warning
                pass
        elif package == APKType.rgc:
            self.find_latest_rgc(architecture)
        elif package == APKType.pd:
            self.find_latest_pd(architecture)

    # @TODO - This function essentially a "simple" download with APKMirror
    def download_pogo(self, architecture: APKArch) -> NoReturn:
        """ Download the package com.nianticlabs.pokemongo

        Determine if theres a newer version of com.nianticlabs.pokemongo.  If a new version exists, validate it is
        supported by MAD.  If the release is supported download and save to the storage interface

        Args:
            architecture (APKArch): Architecture of the package to download
        """
        if not self.api_token:
            logger.warning(
                "The MADdev API token (maddev_api_token) has not been configured in config.ini."
                " Please configure this to use the wizard for downloading PokemonGo."
            )
            return None
        try:
            latest_pogo_info, version_str = self.find_latest_pogo(architecture)
        except SearchError:
            # The error has already been logged as a warning
            return None
        if latest_pogo_info is None:
            logger.warning('Unable to find latest data for PoGo. Try again later')
            return None
        current_version = self.storage.get_current_version(APKType.pogo, architecture)
        if current_version and current_version == version_str:
            logger.info("Latest version of PoGO is already installed")
            return None
        where = {
            'usage': APKType.pogo.value,
            'arch': architecture.value
        }
        logger.info("Starting download of PoGo [{}] {}", version_str, architecture.name)
        update_data = {
            'download_status': 1
        }
        self.dbc.autoexec_update('mad_apk_autosearch', update_data, where_keyvals=where)
        response = perform_http_download(latest_pogo_info.download_url)
        if response is None:
            logger.warning("Unable to successfully download PoGo")
        try:
            PackageImporter(APKType.pogo, architecture, self.storage, io.BytesIO(response.content),
                            'application/vnd.android.package-archive', version=version_str)
        except Exception as err:
            logger.warning("Unable to import the APK. {}", err)
        finally:
            update_data["download_status"] = 0
            self.dbc.autoexec_update('mad_apk_autosearch', update_data, where_keyvals=where)

    def download_pd(self, architecture: APKArch) -> NoReturn:
        """ Download the package com.mad.pogodroid

        Args:
            architecture (APKArch): Architecture of the package to download
        """
        logger.info("Downloading latest PogoDroid")
        self.__download_simple(APKType.pd, architecture)

    def __download_simple(self, package: APKType, architecture: APKArch) -> NoReturn:
        """ Downloads the package via requests

        Determine if there is a newer version of the package.  If there is a newer version, download and save to the
        storage interface

        Args:
            package (APKType): Package to download
            architecture (APKArch): Architecture of the package to download
        """
        latest_data = self.get_latest(package, architecture)
        current_version = self.storage.get_current_version(package, architecture)
        if type(current_version) is not str:
            current_version = None
        if not latest_data or latest_data['url'] is None:
            self.apk_search(package, architecture)
            latest_data = self.get_latest(package, architecture)
        if not latest_data:
            logger.warning('Unable to find latest data')
        elif current_version and 'size' in current_version and current_version.size == int(latest_data['version']):
            logger.info('Latest version already installed')
        else:
            update_data = {
                'download_status': 1
            }
            where = {
                'usage': package.value,
                'arch': architecture.value
            }
            self.dbc.autoexec_update('mad_apk_autosearch', update_data, where_keyvals=where)
            try:
                retries: int = 0
                successful: bool = False
                while retries < MAX_RETRIES and not successful:
                    response = requests.get(latest_data['url'], verify=False, headers=APK_HEADERS)
                    downloaded_file = io.BytesIO(response.content)
                    if downloaded_file and downloaded_file.getbuffer().nbytes > 0:
                        PackageImporter(package, architecture, self.storage, downloaded_file,
                                        'application/vnd.android.package-archive')
                        successful = True
                    else:
                        logger.info("Issue downloading apk")
                        retries += 1
                        if retries < MAX_RETRIES:
                            logger.warning('Unable to successfully download the APK')
            except Exception:  # noqa: E722
                logger.warning('Unable to download the file @ {}', latest_data['url'])
            finally:
                update_data['download_status'] = 0
                self.dbc.autoexec_update('mad_apk_autosearch', update_data, where_keyvals=where)

    def download_rgc(self, architecture: APKArch) -> NoReturn:
        """ Download the package de.grennith.rgc.remotegpscontroller

        Args:
            architecture (APKArch): Architecture of the package to download
        """
        logger.info("Downloading latest RGC")
        self.__download_simple(APKType.rgc, architecture)

    def __find_latest_head(self, package, architecture, url) -> Optional[bool]:
        """ Determine if there is a newer version by checking the size of the package from the HEAD response

        Args:
            package (APKType): Package to download
            architecture (APKArch): Architecture of the package to download
            url (str): URL to perform the HEAD against
        """
        update_available = False
        (packages, status) = lookup_package_info(self.storage, package)
        curr_info = packages[architecture] if packages else None
        if curr_info:
            installed_size = curr_info.size
            curr_info_logstring = f' (old version {curr_info.version} of size {curr_info.size})'
        else:
            installed_size = None
            curr_info_logstring = ''
        head = requests.head(url, verify=False, headers=APK_HEADERS, allow_redirects=True)
        mirror_size = int(head.headers['Content-Length'])
        if not curr_info or (installed_size and installed_size != mirror_size):
            logger.info('Newer version found on the mirror of size {}{}', mirror_size, curr_info_logstring)
            update_available = True
        else:
            logger.info('No newer version found (installed version {} of size {})', curr_info.version, curr_info.size)
        self.set_last_searched(package, architecture, version=mirror_size, url=url)
        return update_available

    def find_latest_pd(self, architecture: APKArch) -> Optional[bool]:
        """ Determine if the package com.mad.pogodroid has an update

        Args:
            architecture (APKArch): Architecture of the package to check
        """
        logger.info('Searching for a new version of PD [{}]', architecture.name)
        return self.__find_latest_head(APKType.pd, architecture, global_variables.URL_PD_APK)

    def find_latest_pogo(self, architecture: APKArch) -> Tuple[PackageVariant, str]:
        """ Determine if the package com.nianticlabs.pokemongo has an update

        Args:
            architecture (APKArch): Architecture of the package to check
        """
        logger.info('Searching for a new version of PoGo [{}]', architecture.name)
        mad_supported_pogo = get_supported_pogo(architecture, self.storage.token())
        # convert to tuple so we can hash it...
        available_apks = get_available_versions(tuple(mad_supported_pogo[architecture]))
        apk_variant = None
        version_str = None
        # This is large enough to be its own function and UT'd
        try:
            for version in mad_supported_pogo[architecture]:
                if version not in available_apks.versions:
                    logger.info("Unable to find Pogo version {} [{}]", version, architecture)
                    continue
                version_data = available_apks.versions[version]
                arch_name = "armeabi-v7a" if architecture == APKArch.armeabi_v7a else "arm64-v8a"
                if arch_name not in version_data.arch:
                    logger.info("Pogo {} [{}] does not exist", version, arch_name)
                    continue
                for variant in version_data.arch[arch_name]:
                    if variant.apk_type != "APK":
                        logger.info("Skipping {} as its not an APK", variant)
                        continue
                    apk_variant = variant
                    version_str = version
                    logger.info("Using Pogo {} [{}]", version, arch_name)
                    raise FoundVaraint
        except FoundVaraint:
            pass
        if not apk_variant:
            logger.warning("Unable to find a suitable download for Pokemon GO [{}]", architecture)
            raise WizardError("Unable to find an APKMirror download for Pokemon GO [{}]", architecture)
        current_version_str = self.storage.get_current_version(APKType.pogo, architecture)
        if current_version_str:
            current_version_code = self.lookup_version_code(current_version_str, architecture)
            if current_version_code is None:
                current_version_code = 0
            latest_vc = apk_variant.version_code
            if latest_vc > current_version_code:
                logger.info("Newer version found: {}", latest_vc)
                generate_download_url_function(apk_variant)
                self.set_last_searched(
                    APKType.pogo,
                    architecture,
                    version=version_str,
                    url=apk_variant.download_url
                )
            elif current_version_code == latest_vc:
                logger.info("Already have the latest version {}", latest_vc)
            else:
                logger.warning("Unable to find a supported version")
        else:
            generate_download_url(apk_variant)
            self.set_last_searched(
                APKType.pogo,
                architecture,
                version=version_str,
                url=apk_variant.download_url
            )
        return (apk_variant, version_str)

    def find_latest_rgc(self, architecture: APKArch) -> Optional[bool]:
        """ Determine if the package de.grennith.rgc.remotegpscontroller has an update

        Args:
            architecture (APKArch): Architecture of the package to check
        """
        logger.info('Searching for a new version of RGC [{}]', architecture.name)
        return self.__find_latest_head(APKType.rgc, architecture, global_variables.URL_RGC_APK)

    def get_latest(self, package: APKType, architecture: APKArch) -> dict:
        """ Determine the latest found version for a given package / architecture

        Args:
            package (APKType): Package to download
            architecture (APKArch): Architecture of the package to download

        Returns (dict):
            Returns the latest version found for the package
        """
        sql = "SELECT `version`, `url` FROM `mad_apk_autosearch` WHERE `usage` = %s AND `arch` = %s"
        return self.dbc.autofetch_row(sql, args=(package.value, architecture.value))

    def parse_version_codes(self, supported_codes: Dict[APKArch, Dict[str, int]]):
        versions: Dict[APKArch, str] = {
            APKArch.armeabi_v7a: {},
            APKArch.arm64_v8a: {}
        }
        for vstr, vcode in supported_codes.items():
            version, arch = vstr.split('_')
            named_arch = APKArch.armeabi_v7a if arch == '32' else APKArch.arm64_v8a
            if named_arch not in versions:
                versions[named_arch] = {}
            versions[named_arch][version] = vcode
        return versions

    def lookup_version_code(self, version_code: str, arch: APKArch) -> Optional[int]:
        named_arch = '32' if arch == APKArch.armeabi_v7a else '64'
        latest_version = f"{version_code}_{named_arch}"
        data = get_version_codes()
        if data:
            try:
                return data[latest_version]
            except KeyError:
                pass
        return 0

    def set_last_searched(self, package: APKType, architecture: APKArch, version: str = None,
                          url: str = None) -> NoReturn:
        """ Updates the last search information for the package / architecture

        Args:
            package (APKType): Package to download
            architecture (APKArch): Architecture of the package to download
            version (str): latest version found
            url (str): URL for the download
        """
        data = {
            'usage': package.value,
            'arch': architecture.value,
            'last_checked': 'NOW()'
        }
        if version:
            data['version'] = version
        if url:
            data['url'] = url
        self.dbc.autoexec_insert('mad_apk_autosearch', data, literals=['last_checked'], optype='ON DUPLICATE')


class PackageImporter(object):
    """ Validates and saves the package to the storage interface

    Args:
        package (APKType): Package to save
        architecture (APKArch): Architecture of the package to save
        storage_obj (AbstractAPKStorage): Storage interface for saving
        downloaded_file (io.BytesIO): binary contents to be saved
        mimetype (str): Mimetype of the package
        version (str): Version of the package
    """
    def __init__(self, package: APKType, architecture: APKArch, storage_obj: AbstractAPKStorage,
                 downloaded_file: io.BytesIO, mimetype: str, version: str = None):
        self.package_version: str = None
        self.package_name: str = None
        self.package_arch: APKArch = None
        self._data: io.BytesIO = downloaded_file
        if mimetype == 'application/vnd.android.package-archive':
            self.package_version, self.package_name = get_apk_info(downloaded_file)
        else:
            self.normalize_package()
            mimetype = 'application/zip'
        if self.package_version:
            if not version:
                version = self.package_version
            try:
                pkg = APKPackage(self.package_name)
            except ValueError:
                raise InvalidFile('Unknown package %s' % (self.package_name))
            if pkg.name != package.name:
                raise WizardError('Attempted to upload %s as %s' % (pkg.name, package.name))
            if self.package_arch and self.package_arch != architecture and architecture != APKArch.noarch:
                msg = 'Attempted to upload {} as an invalid architecture.  Expected {} but received {}'
                raise WizardError(msg.format(pkg.name, architecture.name, self.package_arch.name))
            storage_obj.save_file(package, architecture, version, mimetype, self._data, True)
            log_msg = 'New APK uploaded for {} [{}]'
            logger.info(log_msg, package.name, version)
        else:
            logger.warning('Unable to determine apk information')

    def normalize_package(self) -> NoReturn:
        """ Normalize the package

        Validate that only valid APK files are present within the package and have the correct extension.  Exclude the
        DPI APK as it is not relevant to the installation
        """
        pruned_zip = io.BytesIO()
        zout = zipfile.ZipFile(pruned_zip, 'w')
        with zipfile.ZipFile(self._data) as zip_data:
            for item in zip_data.infolist():
                try:
                    with zip_data.open(item, 'r') as fh:
                        apk = apkutils.APK(io.BytesIO(fh.read()))
                        manifest = apk.get_manifest()
                        try:
                            self.package_version = manifest['@android:versionName']
                            self.package_name = manifest['@package']
                        except KeyError:
                            pass
                    try:
                        filename = manifest['@split']
                        if filename[-3:] == 'dpi':
                            continue
                    except KeyError:
                        filename = item.filename
                    else:
                        try:
                            # The architectures use dash but we are required to use underscores
                            self.package_arch = lookup_arch_enum(filename.rsplit('.', 1)[1].replace('-', '_'))
                        except (IndexError, KeyError, ValueError):
                            pass
                    if filename[-3:] != 'apk':
                        filename += '.apk'
                    zout.writestr(filename, zip_data.read(item.filename))
                except (BadZipFile, LargeZipFile):
                    continue
        zout.close()
        if not self.package_version:
            raise InvalidFile('Unable to extract information from file')
        self._data = pruned_zip


@cachetools.func.ttl_cache(maxsize=1, ttl=10 * 60)
def get_available_versions(versions: Tuple[str]) -> PackageBase:
    """Query apkmirror for the available packages"""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    logger.info("Querying APKMirror for the latest releases")
    try:
        available: Dict[str, PackageBase] = loop.run_until_complete(package_search_match(
            "https://www.apkmirror.com/apk/niantic-inc/pokemon-go/",
            versions=list(versions)
        ))
    except IndexError:
        logger.warning(
            "Unable to query APKMirror. There is probably a recaptcha that needs to be solved and that "
            "functionality is not currently implemented. Please manually download and upload to the wizard"
        )
        raise SearchError
    else:
        logger.info("Successfully queried APKMirror to get the latest releases")
        return available


def generate_download_url_function(apk_variant):
    """Async determine URL"""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    loop.run_until_complete(generate_download_url(apk_variant))
