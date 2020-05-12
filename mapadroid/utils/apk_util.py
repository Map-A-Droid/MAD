import io
import os
import re
import time
from threading import Thread
import zipfile

import flask
import apkutils
import requests
import urllib3
from werkzeug.utils import secure_filename

from mapadroid.utils import global_variables
from mapadroid.utils.logging import logger
from mapadroid.utils.walkerArgs import parseArgs
from gpapi.googleplay import GooglePlayAPI, LoginError, RequestError

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

APK_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows; U; Windows NT 5.1; de; rv:1.9.2.3) Gecko/20100401 Firefox/3.6.3',
}

class GPlayConnector(object):
    def __init__(self, architecture):
        logger.debug('Creating new Google Play API connection')
        args = parseArgs()
        try:
            device_codename = global_variables.MAD_APK_SEARCH[architecture]
        except KeyError:
            logger.critical('Device architecture not defined')
            raise
        self.tmp_folder: str = args.temp_path
        self.api: GooglePlayAPI = GooglePlayAPI(device_codename=device_codename)
        self.connect(args.gmail_user, args.gmail_passwd)

    def connect(self, username: str, password: str) -> bool:
        logger.debug('Attempting GPlay Auth')
        try:
            self.api.login(email=username, password=password)
            logger.debug('GPlay Auth Successful')
            return True
        except LoginError as err:
            logger.warning('Unable to login to GPlay: {}', err)
            raise

    def download(self, packagename: str) -> io.BytesIO:
        details = self.api.details(packagename)
        inmem_zip = io.BytesIO()
        if details['offer'][0]['checkoutFlowRequired']:
            method = self.api.delivery
        else:
            method = self.api.download
        try:
            data_iter = method(packagename, expansion_files=True)
        except IndexError as exc:
            logger.error("Error while downloading %s : this package does not exist, "
                         "try to search it via --search before",
                         packagename)
        except Exception as exc:
            logger.error("Error while downloading %s : %s", packagename, exc)
        additional_data = data_iter['additionalData']
        splits = data_iter['splits']
        total_size = int(data_iter['file']['total_size'])
        chunk_size = int(data_iter['file']['chunk_size'])
        try:
            with zipfile.ZipFile(inmem_zip, "w") as myzip:
                tmp_file = io.BytesIO()
                for index, chunk in enumerate(data_iter['file']['data']):
                    tmp_file.write(chunk)
                tmp_file.seek(0,0)
                myzip.writestr('base.apk', tmp_file.read())
                del tmp_file
                if additional_data:
                    for obb_file in additional_data:
                        obb_filename = "%s.%s.%s.obb" % (obb_file["type"], obb_file["versionCode"], data_iter["docId"])
                        obb_total_size = int(obb_file['file']['total_size'])
                        obb_chunk_size = int(obb_file['file']['chunk_size'])
                        tmp_file = io.BytesIO()
                        for index, chunk in enumerate(obb_file["file"]["data"]):
                            tmp_file.write(chunk)
                        tmp_file.seek(0,0)
                        myzip.writestr(obb_filename, tmp_file.read())
                        del tmp_file
                if splits:
                    for split in splits:
                        split_total_size = int(split['file']['total_size'])
                        split_chunk_size = int(split['file']['chunk_size'])
                        tmp_file = io.BytesIO()
                        for index, chunk in enumerate(split["file"]["data"]):
                            tmp_file.write(chunk)
                        tmp_file.seek(0,0)
                        myzip.writestr(split['name'], tmp_file.read())
                        del tmp_file
        except IOError as exc:
            logger.error("Error while writing {} : {}", packagename, exc)
            return False
        inmem_zip.seek(0,0)
        return inmem_zip

    def get_latest_version(self, query: str) -> str:
        result = self.api.details(query)
        try:
            return result['details']['appDetails']['versionString']
        except:
            return None

class AutoDownloader(object):
    def __init__(self, dbc):
        self.dbc = dbc
        self.gpconn = None

    def apk_all_actions(self):
        self.apk_all_search()
        self.apk_all_download()

    def apk_all_search(self):
        self.find_latest_pogo(global_variables.MAD_APK_ARCH_ARMEABI_V7A)
        self.find_latest_pogo(global_variables.MAD_APK_ARCH_ARM64_V8A)
        self.find_latest_rgc(global_variables.MAD_APK_ARCH_NOARCH)
        self.find_latest_pd(global_variables.MAD_APK_ARCH_NOARCH)

    def apk_all_download(self):
        t = Thread(target=self.apk_nonblocking_download)
        t.start()

    def apk_nonblocking_download(self, ):
        self.download_pogo(global_variables.MAD_APK_ARCH_ARMEABI_V7A)
        self.download_pogo(global_variables.MAD_APK_ARCH_ARM64_V8A)
        self.download_rgc(global_variables.MAD_APK_ARCH_NOARCH)
        self.download_pd(global_variables.MAD_APK_ARCH_NOARCH)

    def apk_search(self, apk_type, architecture):
        if apk_type == global_variables.MAD_APK_USAGE_POGO:
            self.find_latest_pogo(architecture)
        elif apk_type == global_variables.MAD_APK_USAGE_RGC:
            self.find_latest_rgc(architecture)
        elif apk_type == global_variables.MAD_APK_USAGE_PD:
            self.find_latest_pd(architecture)

    def apk_download(self, apk_type, architecture):
        if apk_type == global_variables.MAD_APK_USAGE_POGO:
            self.download_pogo(architecture)
        elif apk_type == global_variables.MAD_APK_USAGE_RGC:
            self.download_rgc(architecture)
        elif apk_type == global_variables.MAD_APK_USAGE_PD:
            self.download_pd(architecture)

    def download_pogo(self, architecture):
        # Determine the version and fileid
        sql = "SELECT `version` FROM `mad_apks` WHERE `usage` = %s AND `arch` = %s"
        current_ver = self.dbc.autofetch_value(sql, args=(global_variables.MAD_APK_USAGE_POGO, architecture))
        latest_data = self.get_latest(global_variables.MAD_APK_USAGE_POGO, architecture)
        if not latest_data or latest_data['url'] is None:
            self.find_latest_pogo(architecture)
            latest_data = self.get_latest(global_variables.MAD_APK_USAGE_POGO, architecture)
        if not latest_data:
            logger.warning('Unable to find latest data for PoGo')
        else:
            if current_ver is None or is_newer_version(latest_data['version'], current_ver):
                where = {
                    'usage': global_variables.MAD_APK_USAGE_POGO,
                    'arch': architecture
                }
                try:
                    update_data = {
                        'download_status': 1
                    }
                    self.dbc.autoexec_update('mad_apk_autosearch', update_data, where_keyvals=where)
                    self.gpconn = GPlayConnector(architecture)
                    downloaded_file = self.gpconn.download('com.nianticlabs.pokemongo')
                    apk = APKDownloader(self.dbc, None, architecture, global_variables.MAD_APK_USAGE_POGO,
                                        filename = 'pogo_%s_%s.zip' % (architecture, latest_data['version'],),
                                        file = downloaded_file,
                                        content_type = 'application/zip')
                    apk.upload_file(skip_check = True, version = latest_data['version'])
                except:
                    raise
                finally:
                    update_data['download_status'] = 0
                    self.dbc.autoexec_update('mad_apk_autosearch', update_data, where_keyvals=where)

    def download_pd(self, architecture):
        logger.info("Downloading latest PogoDroid")
        self.__download_simple(global_variables.MAD_APK_USAGE_PD, architecture)

    def __download_simple(self, apk_type, architecture):
        latest_data = self.get_latest(apk_type, architecture)
        installed = get_mad_apk(self.dbc, apk_type, architecture)
        if not latest_data or latest_data['url'] is None:
            self.apk_search(apk_type, architecture)
            latest_data = self.get_latest(apk_type, architecture)
        if not latest_data:
            logger.warning('Unable to find latest data')
        elif installed and 'size' in installed and installed['size'] == int(latest_data['version']):
            logger.info('Latest version already installed')
        else:
            filename = latest_data['url'].split('/')[-1]
            apk = APKDownloader(self.dbc, latest_data['url'], architecture, apk_type, filename=filename)
            apk.upload_file()

    def download_rgc(self, architecture):
        logger.info("Downloading latest RGC")
        self.__download_simple(global_variables.MAD_APK_USAGE_RGC, architecture)

    def __find_latest_head(self, apk_type, arch, url):
        sql = "SELECT maa.`version` AS 'maa_ver', ma.`version` AS 'ma_ver', fm.`size`\n" \
              "FROM `mad_apk_autosearch` maa\n" \
              "LEFT JOIN `mad_apks` ma ON ma.`usage` = maa.`usage` AND ma.`arch` = maa.`arch`\n" \
              "LEFT JOIN `filestore_meta` fm ON fm.`filestore_id` = ma.`filestore_id`\n" \
              "WHERE maa.`usage` = %s AND maa.`arch` = %s"
        curr_info = self.dbc.autofetch_row(sql, args=(apk_type, arch))
        head = requests.head(url, verify=False, headers=APK_HEADERS, allow_redirects=True)
        installed_size = curr_info.get('size', None)
        mirror_size = int(head.headers['Content-Length'])
        if not curr_info or (installed_size and installed_size != mirror_size):
            logger.info('Newer version found on the mirror of size {}', mirror_size)
        else:
            logger.info('No newer version found')
        self.set_last_searched(apk_type, arch, version=mirror_size, url=url)

    def find_latest_pd(self, architecture):
        logger.info('Searching for a new version of PD [{}]', architecture)
        self.__find_latest_head(global_variables.MAD_APK_USAGE_PD, architecture, global_variables.URL_PD_APK)

    def find_latest_pogo(self, architecture):
        # Determine the version and fileid
        logger.info('Searching for a new version of PoGo [{}]', architecture)
        self.gpconn = GPlayConnector(architecture)
        try:
            download_url = None
            latest = self.gpconn.get_latest_version('com.nianticlabs.pokemongo')
            sql = "SELECT `version` FROM `mad_apks` WHERE `usage` = %s AND `arch` = %s"
            current_ver = self.dbc.autofetch_value(sql, args=(global_variables.MAD_APK_USAGE_POGO, architecture))
            if current_ver is None or is_newer_version(latest, current_ver):
                logger.info('Newer version found on the Play Store: {}', latest)
                download_url = True
            else:
                logger.info('No newer version found')
            self.set_last_searched(global_variables.MAD_APK_USAGE_POGO, architecture, version=latest,
                                   url=download_url)
        except Exception as err:
            logger.critical(err)

    def find_latest_rgc(self, architecture):
        logger.info('Searching for a new version of RGC [{}]', architecture)
        self.__find_latest_head(global_variables.MAD_APK_USAGE_RGC, architecture,
                                global_variables.URL_RGC_APK)

    def get_latest(self, usage, arch):
        sql = "SELECT `version`, `url` FROM `mad_apk_autosearch` WHERE `usage` = %s AND `arch` = %s"
        return self.dbc.autofetch_row(sql, args=(usage, arch))

    def set_last_searched(self, usage, arch, version: str = None, url: str = None):
        data = {
            'usage': usage,
            'arch': arch,
            'last_checked': 'NOW()'
        }
        if version:
            data['version'] = version
        if url:
            data['url'] = url
        self.dbc.autoexec_insert('mad_apk_autosearch', data, literals=['last_checked'], optype='ON DUPLICATE')


class APKDownloader(object):
    def __init__(self, dbc, url: str, architecture: int, apk_type: int,
                 filename: str = None,
                 file: io.BytesIO = None,
                 content_type: str = None):
        self.dbc = dbc
        self.url = url
        self.apk_type = apk_type
        self.architecture = architecture
        self.file = None
        self.content_type = None
        self.filename = filename
        if not file:
            self.__download_file()
        else:
            self.content_type = content_type
            self.file = file

    def __download_file(self):
        update_data = {
            'download_status': 1
        }
        where = {
            'usage': self.apk_type,
            'arch': self.architecture
        }
        self.dbc.autoexec_update('mad_apk_autosearch', update_data, where_keyvals=where)
        try:
            r = requests.get(self.url, verify=False, headers=APK_HEADERS)
            self.file = io.BytesIO(r.content)
            try:
                if not self.filename:
                    self.filename = re.findall("filename=(.+)", r.headers['content-disposition'])[0]
            except:
                self.filename = self.filename if self.filename else self.url
            self.content_type = 'application/vnd.android.package-archive'
        except:
            logger.warning('Unable to download the file @ {}', self.url)
        finally:
            update_data['download_status'] = 0
            self.dbc.autoexec_update('mad_apk_autosearch', update_data, where_keyvals=where)

    def upload_file(self, skip_check: bool = False, version: str = None):
        if self.content_type:
            MADAPKImporter(self.dbc, self.filename, self.file, self.content_type, apk_type=self.apk_type,
                           architecture=self.architecture, mad_apk=True, skip_check = skip_check,
                           version = version)


class MADAPKImporter(object):
    def __init__(self, dbc, filename: str, apk_file, content_type, apk_type: int = None,
                 architecture: int = None,
                 mad_apk: bool = False,
                 skip_check: bool = False,
                 version: str = None):
        self.dbc = dbc
        self.filename = secure_filename(filename)
        self.apk_type = apk_type
        self.architecture = architecture
        self.content_type = content_type
        self.mad_apk = mad_apk
        self.package = None
        self.version = version
        self.__valid = True
        if not skip_check:
            self.__validate_file(apk_file)
        self.__import_file(apk_file)

    def __import_file(self, apk_file):
        if self.__valid:
            try:
                filestore_id = None
                # Determine if we already have this file-type uploaded.  If so, remove it once the new one is
                # completed and update the id
                if self.mad_apk and self.apk_type is not None and self.architecture is not None:
                    filestore_id_sql = "SELECT `filestore_id` FROM `mad_apks` WHERE `usage` = %s AND `arch` = %s"
                    filestore_id = self.dbc.autofetch_value(filestore_id_sql,
                                                            args=(self.apk_type, self.architecture,))
                    if filestore_id:
                        delete_data = {
                            'filestore_id': filestore_id
                        }
                        self.dbc.autoexec_delete('filestore_meta', delete_data)
                apk_file.seek(0, os.SEEK_END)
                file_length = apk_file.tell()
                # Check to see if the filename exists.  If it does, rename it
                sql = 'SELECT `filestore_id` FROM `filestore_meta` WHERE `filename` = %s'
                exists = self.dbc.autofetch_value(sql, args=(self.filename,))
                if exists:
                    self.filename = '%s_%s' % (int(time.time()), self.filename)
                insert_data = {
                    'filename': self.filename,
                    'size': file_length,
                    'mimetype': self.content_type,
                }
                new_id = self.dbc.autoexec_insert('filestore_meta', insert_data)
                insert_data = {
                    'filestore_id': new_id,
                    'usage': self.apk_type,
                    'arch': self.architecture,
                    'version': self.version,
                }
                self.dbc.autoexec_insert('mad_apks', insert_data, optype='ON DUPLICATE')
                apk_file.seek(0, 0)
                logger.info('Starting upload of APK')
                while True:
                    chunked_data = apk_file.read(global_variables.CHUNK_MAX_SIZE)
                    if not chunked_data:
                        break
                    insert_data = {
                        'filestore_id': new_id,
                        'size': len(chunked_data),
                        'data': chunked_data
                    }
                    self.dbc.autoexec_insert('filestore_chunks', insert_data)
                logger.info('Finished upload of APK')
            except Exception as err:
                logger.exception('Unable to save the apk', exc_info=True)

    def __validate_file(self, apk_file):
        try:
            apk = apkutils.APK(apk_file)
        except:
            logger.warning('Unable to parse APK file')
            self.valid = False
        else:
            self.version = apk.get_manifest()['@android:versionName']
            self.package = apk.get_manifest()['@package']
            log_msg = 'New APK uploaded for {}'
            args = [self.filename]
            if self.architecture:
                log_msg += ' {}'
                args.append(self.architecture)
            log_msg += ' [{}]'
            args.append(self.version)
            logger.info(log_msg, *args)


def chunk_generator(dbc, filestore_id):
    sql = "SELECT `chunk_id` FROM `filestore_chunks` WHERE `filestore_id` = %s"
    data_sql = "SELECT `data` FROM `filestore_chunks` WHERE `chunk_id` = %s"
    chunk_ids = dbc.autofetch_column(sql, args=(filestore_id,))
    for chunk_id in chunk_ids:
        yield dbc.autofetch_value(data_sql, args=(chunk_id))

def get_apk_list(dbc, apk_type, apk_arch):
    apks = get_mad_apks(dbc)
    try:
        apks[apk_type]
        try:
            if apks[apk_type][apk_arch]['version'] != None:
                return (apks[apk_type][apk_arch], 200)
            else:
                return ('MAD APK for %s has not been uploaded' % (apk_type,), 404)
        except:
            if apk_arch:
                return ('Invalid arch_type.  Valid arch_types: %s' % apks[apk_type].keys(), 404)
            elif len(apks[apk_type]) == 1:
                key = list(apks[apk_type].keys())[0]
                if apks[apk_type][key]['version'] != None:
                    return (apks[apk_type][key], 200)
                return ('MAD APK for %s has not been uploaded' % (apk_type,), 404)
            else:
                return (apks[apk_type], 200)
    except:
        if apk_type:
            return ('Invalid apk_type.  Valid apk_types: %s' % apks.keys(), 404)
        else:
            return (apks, 200)

def get_mad_apks(db) -> dict:
    apks = {
        global_variables.MAD_APK_USAGE_POGO: {
            global_variables.MAD_APK_ARCH_ARMEABI_V7A: {
                'version': None,
                'file_id': None,
                'filename': None,
                'arch_disp': 'armeabi-v7a',
                'usage_disp': 'pogo'
            },
            global_variables.MAD_APK_ARCH_ARM64_V8A: {
                'version': None,
                'file_id': None,
                'filename': None,
                'arch_disp': 'arm64-v8a',
                'usage_disp': 'pogo'
            },
        },
        global_variables.MAD_APK_USAGE_RGC: {
            global_variables.MAD_APK_ARCH_NOARCH: {
                'version': None,
                'file_id': None,
                'filename': None,
                'arch_disp': 'noarch',
                'usage_disp': 'rgc'
            },
        },
        global_variables.MAD_APK_USAGE_PD: {
            global_variables.MAD_APK_ARCH_NOARCH: {
                'version': None,
                'file_id': None,
                'filename': None,
                'arch_disp': 'noarch',
                'usage_disp': 'pogodroid'
            },
        }
    }
    sql = "SELECT * FROM `mad_apks`"
    file_sql = "SELECT `filename`, `size`, `mimetype` FROM `filestore_meta` WHERE `filestore_id` = %s"
    mad_apks = db.autofetch_all(sql)
    for apk in mad_apks:
        apk_type = None
        apk_arch = None
        file_data = db.autofetch_row(file_sql, args=(apk['filestore_id']))
        if apk['usage'] == global_variables.MAD_APK_USAGE_POGO:
            apk_name = 'pogo'
            if apk['arch'] == global_variables.MAD_APK_ARCH_ARMEABI_V7A:
                apk_arch = 'armeabi-v7a'
            else:
                apk_arch = 'arm64-v8a'
        elif apk['usage'] == global_variables.MAD_APK_USAGE_RGC:
            apk_name = 'rgc'
            apk_arch = 'noarch'
        elif apk['usage'] == global_variables.MAD_APK_USAGE_PD:
            apk_name = 'pogodroid'
            apk_arch = 'noarch'
        file_data['version'] = apk['version']
        file_data['file_id'] = apk['filestore_id']
        file_data['arch_disp'] = apk_arch
        file_data['usage_disp'] = apk_name
        apks[apk['usage']][apk['arch']] = file_data
    return apks


def get_mad_apk(db, apk_type, architecture='noarch') -> dict:
    apks = get_mad_apks(db)
    apk_type, apk_arch = convert_to_backend(apk_type=apk_type, apk_arch=architecture)
    try:
        return apks[global_variables.MAD_APK_USAGE[apk_type]][apk_arch]
    except KeyError:
        try:
            return apks[apk_type][apk_arch]
        except:
            pass
        if apk_arch != global_variables.MAD_APK_ARCH_NOARCH:
            return get_mad_apk(db, apk_type)
        else:
            return False


def get_mad_apk_ver(db, apk_type: str, apk_arch: str = 'noarch') -> str:
    apks = get_mad_apks(db)
    try:
        return get_mad_apk(db, apk_type, apk_arch=apk_arch)['version']
    except KeyError:
        return False


def is_newer_version(first_ver: str, second_ver: str) -> bool:
    """ Determines if the first version is newer than the second """
    first_is_newer = False
    if first_ver == second_ver:
        return None
    split_first_ver = first_ver.split('.')
    solution = False
    try:
        split_second_ver = second_ver.split('.')
        for ind, val in enumerate(split_first_ver):
            if int(val) < int(split_first_ver[ind]):
                solution = True
                break
    except (AttributeError, KeyError):
        pass
    if not solution:
        first_is_newer = True
    return first_is_newer

def convert_to_backend(apk_type=None, apk_arch=None):
    if apk_type and isinstance(apk_type, str):
        try:
            apk_type = int(apk_type)
        except ValueError:
            if apk_type == 'pogo':
                apk_type = global_variables.MAD_APK_USAGE_POGO
            elif apk_type == 'rgc':
                apk_type = global_variables.MAD_APK_USAGE_RGC
            elif apk_type == 'pogodroid':
                apk_type = global_variables.MAD_APK_USAGE_PD
            else:
                apk_type = None
    if apk_arch and isinstance(apk_arch, str):
        try:
            apk_arch = int(apk_arch)
        except ValueError:
            if apk_arch == 'armeabi-v7a':
                apk_arch = global_variables.MAD_APK_ARCH_ARMEABI_V7A
            elif apk_arch == 'arm64-v8a':
                apk_arch = global_variables.MAD_APK_ARCH_ARM64_V8A
            elif apk_arch == 'noarch':
                apk_arch = global_variables.MAD_APK_ARCH_NOARCH
            else:
                global_variables.MAD_APK_ARCH_NOARCH
    return (apk_type, apk_arch)

def download_file(dbc, apk_type, apk_arch):
    apks = get_apk_list(dbc, apk_type, apk_arch)
    if (apks[1]) == 200:
        mad_apk = apks[0]
        return flask.Response(
            flask.stream_with_context(chunk_generator(dbc, mad_apk['file_id'])),
            content_type=mad_apk['mimetype'],
            headers={
                'Content-Disposition': f'attachment; filename=%s' % (mad_apk['filename'])
            }
        )
    else:
        return flask.Response(status=404)
