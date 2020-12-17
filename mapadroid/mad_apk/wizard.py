import io
import json
import zipfile
from threading import Thread
from typing import Dict, NoReturn, Optional

import apkutils
import requests
import urllib3
from apkutils.apkfile import BadZipFile, LargeZipFile

from mapadroid.utils import global_variables
from mapadroid.utils.gplay_connector import GPlayConnector
from mapadroid.utils.logging import LoggerEnums, get_logger

from .abstract_apk_storage import AbstractAPKStorage
from .apk_enums import APKArch, APKPackage, APKType
from .utils import (get_apk_info, is_newer_version, lookup_arch_enum,
                    lookup_package_info, supported_pogo_version)

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


class APKWizard(object):
    """ The wizard will allow for simplified APK management for the required packages

    Args:
        dbc: Database wrapper
        storage: Abstract storage element for interacting with storage medium

    Attributes:
        dbc: Database wrapper
        gpconn: Object for interacting with google play
        storage: Abstract storage element for interacting with storage medium
    """
    gpconn: GPlayConnector
    storage: AbstractAPKStorage

    def __init__(self, dbc, storage: AbstractAPKStorage):
        self.storage: AbstractAPKStorage = storage
        self.dbc = dbc
        self.gpconn = None

    def apk_all_actions(self) -> NoReturn:
        "Search and download all required packages"
        self.apk_all_download()

    def apk_all_download(self) -> NoReturn:
        "Download all packages in a non-blocking fashion"
        Thread(target=self.apk_nonblocking_download).start()

    def apk_all_search(self) -> NoReturn:
        "Search for updates for any required package"
        self.find_latest_pogo(APKArch.armeabi_v7a)
        self.find_latest_pogo(APKArch.arm64_v8a)
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
        self.download_rgc(APKArch.noarch)
        self.download_pd(APKArch.noarch)

    def apk_search(self, package: APKType, architecture: APKArch) -> NoReturn:
        """ Search for a specific package

        Args:
            package (APKType): Package to search
            architecture (APKArch): Architecture of the package to search
        """
        if package == APKType.pogo:
            self.find_latest_pogo(architecture)
        elif package == APKType.rgc:
            self.find_latest_rgc(architecture)
        elif package == APKType.pd:
            self.find_latest_pd(architecture)

    def download_pogo(self, architecture: APKArch) -> NoReturn:
        """ Download the package com.nianticlabs.pokemongo

        Determine if theres a newer version of com.nianticlabs.pokemongo.  If a new version exists, validate it is
        supported by MAD.  If the release is supported download and save to the storage interface

        Args:
            architecture (APKArch): Architecture of the package to download
        """
        latest_pogo_info = self.find_latest_pogo(architecture)
        if latest_pogo_info is None:
            logger.warning('Unable to find latest data for PoGo. Try again later')
        elif supported_pogo_version(architecture, latest_pogo_info["version"]):
            latest_version = latest_pogo_info["version"]
            current_version = self.storage.get_current_version(APKType.pogo, architecture)
            if type(current_version) is not str:
                current_version = None
            if current_version is None or is_newer_version(latest_version, current_version):
                where = {
                    'usage': APKType.pogo.value,
                    'arch': architecture.value
                }
                try:
                    update_data = {
                        'download_status': 1
                    }
                    self.dbc.autoexec_update('mad_apk_autosearch', update_data, where_keyvals=where)
                    retries: int = 0
                    successful: bool = False
                    while retries < MAX_RETRIES and not successful:
                        self.gpconn = GPlayConnector(architecture)
                        latest_data = self.get_latest(APKType.pogo, architecture)
                        downloaded_file = self.gpconn.download(APKPackage.pogo.value, version_code=latest_data['url'])
                        if downloaded_file and downloaded_file.getbuffer().nbytes > 0:
                            version, _ = get_apk_info(downloaded_file)
                            if version != latest_version:
                                msg = f"Playstore returned {version} when requesting {latest_version}"
                                logger.warning(msg)
                                raise InvalidDownload(msg)
                            else:
                                PackageImporter(APKType.pogo, architecture, self.storage, downloaded_file,
                                                'application/zip', version=latest_version)
                                successful = True
                        if not successful:
                            logger.info("Issue downloading apk")
                            retries += 1
                            if retries < MAX_RETRIES:
                                logger.warning('Unable to successfully download the APK')
                except Exception:  # noqa: E722
                    raise
                finally:
                    update_data['download_status'] = 0
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

    def __find_latest_head(self, package, architecture, url) -> NoReturn:
        """ Determine if there is a newer version by checking the size of the package from the HEAD response

        Args:
            package (APKType): Package to download
            architecture (APKArch): Architecture of the package to download
            url (str): URL to perform the HEAD against
        """
        (curr_info, status) = lookup_package_info(self.storage, package)
        installed_size = None
        if curr_info:
            installed_size = curr_info.get('size', None)
        head = requests.head(url, verify=False, headers=APK_HEADERS, allow_redirects=True)
        mirror_size = int(head.headers['Content-Length'])
        if not curr_info or (installed_size and installed_size != mirror_size):
            logger.info('Newer version found on the mirror of size {}', mirror_size)
        else:
            logger.info('No newer version found')
        self.set_last_searched(package, architecture, version=mirror_size, url=url)

    def find_latest_pd(self, architecture: APKArch) -> Optional[str]:
        """ Determine if the package com.mad.pogodroid has an update

        Args:
            architecture (APKArch): Architecture of the package to check
        """
        logger.info('Searching for a new version of PD [{}]', architecture.name)
        self.__find_latest_head(APKType.pd, architecture, global_variables.URL_PD_APK)

    def find_latest_pogo(self, architecture: APKArch) -> Optional[str]:
        """ Determine if the package com.nianticlabs.pokemongo has an update

        Args:
            architecture (APKArch): Architecture of the package to check
        """
        latest = None
        version_code: int = None
        version_str: str = None
        logger.info('Searching for a new version of PoGo [{}]', architecture.name)
        try:
            latest_pogo_version = self.get_latest_version()
            if latest_pogo_version[architecture] is None:
                return latest
            latest_supported = latest_pogo_version[architecture]
            current_version = self.storage.get_current_version(APKType.pogo, architecture)
            if type(current_version) is not str:
                current_version = None
            # do some sanity checking until this is fixed properly
            tmp_latest = self.get_latest(APKType.pogo, architecture)
            if current_version is None or is_newer_version(latest_supported["version"], current_version) or (
                    tmp_latest and tmp_latest['url'] is not None):
                # Validate its available via google
                gpconn = GPlayConnector(architecture)
                (store_vc, store_vs) = gpconn.get_latest_version(APKPackage.pogo.value)
                if store_vc < latest_supported["versionCode"]:
                    logger.info(f"Latest supported is {store_vc} while installed is {latest_supported['versionCode']}. "
                                "Unable to find a newer version")
                    return None
                elif store_vc > latest_supported["versionCode"]:
                    logger.info("Version in store is newer than supported version. Using an older version")
                    version_code = latest_supported["versionCode"]
                    version_str = latest_supported["version"]
                elif current_version and store_vs == current_version:
                    logger.info("Latest version [{}] is already installed", store_vc)
                    version_code = store_vc
                    version_str = store_vs
                else:
                    logger.info('Newer version found: {}', store_vs)
                    version_code = store_vc
                    version_str = store_vs
            else:
                logger.info('No newer version found')
            self.set_last_searched(APKType.pogo, architecture, version=version_str, url=version_code)
        except Exception as err:
            logger.opt(exception=True).critical(err)
        return {
            "version_code": version_code,
            "version": version_str
        }

    def find_latest_rgc(self, architecture: APKArch) -> Optional[str]:
        """ Determine if the package de.grennith.rgc.remotegpscontroller has an update

        Args:
            architecture (APKArch): Architecture of the package to check
        """
        logger.info('Searching for a new version of RGC [{}]', architecture.name)
        self.__find_latest_head(APKType.rgc, architecture, global_variables.URL_RGC_APK)

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

    def get_latest_version(self) -> Dict[APKArch, str]:
        versions: Dict[APKArch, str] = {
            APKArch.armeabi_v7a: None,
            APKArch.arm64_v8a: None
        }
        gh_resp = requests.get(global_variables.VERSIONCODES_URL)
        for ver_identifier, version_code in gh_resp.json().items():
            version, arch = ver_identifier.split('_')
            named_arch = APKArch.armeabi_v7a if arch == '32' else APKArch.arm64_v8a
            if versions[named_arch] is None:
                versions[named_arch] = {
                    "versionCode": version_code,
                    "version": version
                }
            elif is_newer_version(version, versions[named_arch]["version"]):
                versions[named_arch] = {
                    "versionCode": version_code,
                    "version": version
                }
        return versions

    def get_version_code(self, latest_supported: Dict[APKArch, str], arch: APKArch) -> Optional[int]:
        pogo_vc_sess = requests.session()
        pogo_vc_sess.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
        })
        # attempt to pull the information locally
        try:
            with open('configs/version_codes.json', 'r') as fh:
                data = json.load(fh)
        except (FileNotFoundError, json.decoder.JSONDecodeError):
            pass
        else:
            version_code = self.parse_version_code(latest_supported, arch, data)
            if version_code is not None:
                return version_code
        # match not found locally.  Try GitHub
        try:
            data = pogo_vc_sess.get(global_variables.VERSIONCODES_GITHUB).json()
        except Exception:
            pass
        else:
            version_code = self.parse_version_code(latest_supported, arch, data)
            if version_code is not None:
                return version_code
        return None

    def parse_version_code(self, latest_supported: Dict[APKArch, str], arch: APKArch, data: Dict) -> Optional[int]:
        named_arch = '32' if arch == APKArch.armeabi_v7a else '64'
        latest_version = f"{latest_supported[arch]}_{named_arch}"
        if data:
            try:
                return data[latest_version]
            except KeyError:
                pass
        return None

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
