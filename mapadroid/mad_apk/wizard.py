import apkutils
import io
import requests
from threading import Thread
from typing import NoReturn, Optional
import urllib3
from .abstract_apk_storage import AbstractAPKStorage
from .apk_enums import APK_Arch, APK_Type, APK_Package
from .utils import lookup_package_info, is_newer_version, supported_pogo_version
from mapadroid.utils import global_variables
from mapadroid.utils.gplay_connector import GPlayConnector
from mapadroid.utils.logging import logger

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

APK_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows; U; Windows NT 5.1; de; rv:1.9.2.3) Gecko/20100401 Firefox/3.6.3',
}
MAX_RETRIES: int = 3  # Number of attempts for downloading on failure


class APKWizard(object):
    gpconn: GPlayConnector
    storage: AbstractAPKStorage

    def __init__(self, dbc, storage: AbstractAPKStorage):
        self.storage: AbstractAPKStorage = storage
        self.dbc = dbc
        self.gpconn = None

    def apk_all_actions(self) -> NoReturn:
        self.apk_all_search()
        self.apk_all_download()

    def apk_all_download(self) -> NoReturn:
        t = Thread(target=self.apk_nonblocking_download)
        t.start()

    def apk_all_search(self) -> NoReturn:
        self.find_latest_pogo(APK_Arch.armeabi_v7a)
        self.find_latest_pogo(APK_Arch.arm64_v8a)
        self.find_latest_rgc(APK_Arch.noarch)
        self.find_latest_pd(APK_Arch.noarch)

    def apk_download(self, package: APK_Type, architecture: APK_Arch) -> NoReturn:
        if package == APK_Type.pogo:
            self.download_pogo(architecture)
        elif package == APK_Type.rgc:
            self.download_rgc(architecture)
        elif package == APK_Type.pd:
            self.download_pd(architecture)

    def apk_nonblocking_download(self) -> NoReturn:
        self.download_pogo(APK_Arch.armeabi_v7a)
        self.download_pogo(APK_Arch.arm64_v8a)
        self.download_rgc(APK_Arch.noarch)
        self.download_pd(APK_Arch.noarch)

    def apk_search(self, package: APK_Type, architecture: APK_Arch) -> NoReturn:
        if package == APK_Type.pogo:
            self.find_latest_pogo(architecture)
        elif package == APK_Type.rgc:
            self.find_latest_rgc(architecture)
        elif package == APK_Type.pd:
            self.find_latest_pd(architecture)

    def download_pogo(self, architecture: APK_Arch) -> NoReturn:
        latest_version = self.find_latest_pogo(architecture)
        if latest_version is None:
            logger.warning('Unable to find latest data for PoGo.  Try again later')
        elif supported_pogo_version(architecture, latest_version):
            current_version = self.storage.get_current_version(APK_Type.pogo, architecture)
            if type(current_version) is not str:
                current_version = None
            if current_version is None or is_newer_version(latest_version, current_version):
                where = {
                    'usage': APK_Type.pogo.value,
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
                        downloaded_file = self.gpconn.download(APK_Package.pogo.value)
                        if downloaded_file and downloaded_file.getbuffer().nbytes > 0:
                            PackageImporter(APK_Type.pogo, architecture, self.storage, downloaded_file,
                                            'application/zip', version=latest_version)
                            successful = True
                        else:
                            logger.info("Issue downloading apk")
                            retries += 1
                            if retries < MAX_RETRIES:
                                logger.warning('Unable to successfully download the APK')
                except:  # noqa: E722
                    raise
                finally:
                    update_data['download_status'] = 0
                    self.dbc.autoexec_update('mad_apk_autosearch', update_data, where_keyvals=where)

    def download_pd(self, architecture: APK_Arch) -> NoReturn:
        logger.info("Downloading latest PogoDroid")
        self.__download_simple(APK_Type.pd, architecture)

    def __download_simple(self, package: APK_Type, architecture: APK_Arch) -> NoReturn:
        latest_data = self.get_latest(package, architecture)
        current_version = self.storage.get_current_version(package, architecture)
        if type(current_version) is not str:
            current_version = None
        if not latest_data or latest_data['url'] is None:
            self.apk_search(package, architecture)
            latest_data = self.get_latest(package, architecture)
        if not latest_data:
            logger.warning('Unable to find latest data')
        elif current_version and 'size' in current_version and current_version['size'] == int(latest_data['version']):
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
                    r = requests.get(latest_data['url'], verify=False, headers=APK_HEADERS)
                    downloaded_file = io.BytesIO(r.content)
                    if downloaded_file and downloaded_file.getbuffer().nbytes > 0:
                        PackageImporter(package, architecture, self.storage, downloaded_file,
                                        'application/vnd.android.package-archive')
                        successful = True
                    else:
                        logger.info("Issue downloading apk")
                        retries += 1
                        if retries < MAX_RETRIES:
                            logger.warning('Unable to successfully download the APK')
            except:  # noqa: E722
                logger.warning('Unable to download the file @ {}', latest_data['url'])
            finally:
                update_data['download_status'] = 0
                self.dbc.autoexec_update('mad_apk_autosearch', update_data, where_keyvals=where)

    def download_rgc(self, architecture: APK_Arch) -> NoReturn:
        logger.info("Downloading latest RGC")
        self.__download_simple(APK_Type.rgc, architecture)

    def __find_latest_head(self, apk_type, arch, url) -> NoReturn:
        (curr_info, status) = lookup_package_info(self.storage, apk_type)
        installed_size = None
        if curr_info:
            installed_size = curr_info.get('size', None)
        head = requests.head(url, verify=False, headers=APK_HEADERS, allow_redirects=True)
        mirror_size = int(head.headers['Content-Length'])
        if not curr_info or (installed_size and installed_size != mirror_size):
            logger.info('Newer version found on the mirror of size {}', mirror_size)
        else:
            logger.info('No newer version found')
        self.set_last_searched(apk_type, arch, version=mirror_size, url=url)

    def find_latest_pd(self, architecture: APK_Arch) -> Optional[str]:
        logger.info('Searching for a new version of PD [{}]', architecture.name)
        self.__find_latest_head(APK_Type.pd, architecture, global_variables.URL_PD_APK)

    def find_latest_pogo(self, architecture: APK_Arch) -> Optional[str]:
        latest = None
        logger.info('Searching for a new version of PoGo [{}]', architecture.name)
        self.gpconn = GPlayConnector(architecture)
        try:
            download_url = None
            latest = self.gpconn.get_latest_version(APK_Package.pogo.value)
            current_version = self.storage.get_current_version(APK_Type.pogo, architecture)
            if type(current_version) is not str:
                current_version = None
            if current_version is None or is_newer_version(latest, current_version):
                if supported_pogo_version(architecture, latest):
                    logger.info('Newer version found on the Play Store: {}', latest)
                    download_url = True
            else:
                logger.info('No newer version found')
            self.set_last_searched(APK_Type.pogo, architecture, version=latest, url=download_url)
        except Exception as err:
            logger.opt(exception=True).critical(err)
        return latest

    def find_latest_rgc(self, architecture: APK_Arch) -> Optional[str]:
        logger.info('Searching for a new version of RGC [{}]', architecture.name)
        self.__find_latest_head(APK_Type.rgc, architecture, global_variables.URL_RGC_APK)

    def get_latest(self, package: APK_Type, architecture: APK_Arch) -> dict:
        sql = "SELECT `version`, `url` FROM `mad_apk_autosearch` WHERE `usage` = %s AND `arch` = %s"
        return self.dbc.autofetch_row(sql, args=(package.value, architecture.value))

    def set_last_searched(self, package: APK_Type, architecture: APK_Arch, version: str = None,
                          url: str = None) -> NoReturn:
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
    def __init__(self, package: APK_Type, architecture: APK_Arch, storage_obj: AbstractAPKStorage, downloaded_file,
                 mimetype: str, version: str = None):
        if mimetype == 'application/vnd.android.package-archive':
            try:
                apk = apkutils.APK(downloaded_file)
            except:  # noqa: E722
                logger.warning('Unable to parse APK file')
            else:
                version = apk.get_manifest()['@android:versionName']
                log_msg = 'New APK uploaded for {}'
                args = [package.name]
                if architecture:
                    log_msg += ' {}'
                    args.append(architecture.name)
                args.append(version)
                logger.info(log_msg, *args)
                storage_obj.save_file(package, architecture, version, mimetype, downloaded_file, True)
        else:
            storage_obj.save_file(package, architecture, version, mimetype, downloaded_file, True)
