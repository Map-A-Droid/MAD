import base64
import io
import json
import os
import re
import warnings
import zipfile
from typing import Callable, List

from google.protobuf.message import DecodeError
from gpapi.googleplay import GooglePlayAPI, LoginError

from mapadroid.mad_apk import APKArch, DeviceCodename
from mapadroid.utils.logging import LoggerEnums, get_logger
from mapadroid.utils.token_dispenser import TokenDispenser
from mapadroid.utils.walkerArgs import parse_args

logger = get_logger(LoggerEnums.utils)


class GPlayConnector(object):
    def __init__(self, architecture: APKArch):
        logger.debug('Creating new Google Play API connection')
        args = parse_args()
        self.token_list = []
        self.token = None
        self.gsfid = None
        self.email = None
        self.valid = False
        try:
            device_codename = getattr(DeviceCodename, architecture.name).value
        except ValueError:
            logger.critical('Device architecture not defined')
            raise
        self.api: GooglePlayAPI = GooglePlayAPI(device_codename=device_codename)
        if args.gmail_user:
            self.connect_gmail(args.gmail_user, args.gmail_passwd)
        else:
            self.token_list = self.generate_token_list(args)
            if not self.check_cached_tokens(args):
                self.generate_new_tokens(args)

    def connect_gmail(self, username: str, password: str) -> bool:
        logger.debug('Attempting GPlay Auth')
        try:
            self.api.login(email=username, password=password)
            logger.debug('GPlay Auth Successful')
            return True
        except LoginError as err:
            logger.warning('Unable to login to GPlay: {}', err)
            raise

    def download(self, packagename: str, method: Callable = None, version_code=None) -> io.BytesIO:
        details = self.api.details(packagename)
        inmem_zip = io.BytesIO()
        with warnings.catch_warnings():
            warnings.simplefilter('ignore', RuntimeWarning)
            if not method:
                if details['offer'][0]['checkoutFlowRequired']:
                    method = self.api.delivery
                else:
                    method = self.api.download
            logger.info('Starting download for {}', packagename)
            try:
                data_iter = method(packagename, expansion_files=True, versionCode=version_code)
            except IndexError:
                logger.error("Unable to find the package. Maybe it no longer is a supported device?")
                return False
            except DecodeError:
                # RPi have an issue where they seem to only support delivery and not download
                return self.download(packagename, method=self.api.delivery, version_code=version_code)
            except Exception as exc:
                logger.opt(exception=True).error("Error while downloading {} : {}", packagename, exc)
                return False
        additional_data = data_iter['additionalData']
        splits = data_iter['splits']
        try:
            with zipfile.ZipFile(inmem_zip, "w") as myzip:
                tmp_file = io.BytesIO()
                for _index, chunk in enumerate(data_iter['file']['data']):
                    tmp_file.write(chunk)
                tmp_file.seek(0, 0)
                myzip.writestr('base.apk', tmp_file.read())
                del tmp_file
                if additional_data:
                    for obb_file in additional_data:
                        obb_filename = "%s.%s.%s.obb" % (obb_file["type"], obb_file["versionCode"], data_iter["docId"])
                        tmp_file = io.BytesIO()
                        for _index, chunk in enumerate(obb_file["file"]["data"]):
                            tmp_file.write(chunk)
                        tmp_file.seek(0, 0)
                        myzip.writestr(obb_filename, tmp_file.read())
                        del tmp_file
                if splits:
                    for split in splits:
                        if re.match(r'config.\w\w$', split['name']):
                            continue
                        tmp_file = io.BytesIO()
                        for _index, chunk in enumerate(split["file"]["data"]):
                            tmp_file.write(chunk)
                        tmp_file.seek(0, 0)
                        myzip.writestr(split['name'], tmp_file.read())
                        del tmp_file
        except IOError as exc:
            logger.error("Error while writing {} : {}", packagename, exc)
            return False
        inmem_zip.seek(0, 0)
        logger.info('Download finished for {}', packagename)
        return inmem_zip

    def get_latest_version(self, query: str) -> str:
        result = self.api.details(query)
        try:
            return (result['details']['appDetails']['versionCode'], result['details']['appDetails']['versionString'])
        except (KeyError, TypeError):
            return None

    # =============================
    # ====== Token Functions ======
    # =============================
    def cache_get_name(self, host):
        return 'cache.{}'.format(base64.b64encode(host.encode()).decode("utf-8"))

    def check_cached_tokens(self, args) -> bool:
        for host in self.token_list:
            parsed_name = self.cache_get_name(host)
            cache_filepath = '{}/{}'.format(args.temp_path, parsed_name)
            if not self.retrieve_token(host, args):
                continue
            if not self.connect_token():
                logger.debug('Unable to login with the token.')
                os.unlink(cache_filepath)
            else:
                logger.info(f"Successfully logged in via token @ {host}")
                return True
        return False

    def connect_token(self):
        try:
            self.api.login(gsfId=self.gsfid, authSubToken=self.token)
            self.valid = True
        except Exception as err:
            logger.debug('Unable to login, {}', err)
        return self.valid

    def get_cached_token(self, host, args):
        parsed_name = self.cache_get_name(host)
        cache_filepath = '{}/{}'.format(args.temp_path, parsed_name)
        token = None
        gsfid = None
        email = None
        try:
            with open(cache_filepath, 'rb') as cached_file:
                cached = json.load(cached_file)
                token = cached['token']
                gsfid = cached['gsfid']
                email = cached['email']
        except FileNotFoundError:
            logger.debug('Cached data for {} not found', host)
        except (json.decoder.JSONDecodeError, KeyError):
            logger.debug('Corrupted cached file found, {}', cache_filepath)
            os.unlink(cache_filepath)
        return token, gsfid, email

    def generate_new_tokens(self, args) -> bool:
        """ Iterate over the available dispensers and cache the first successful connection"""
        for host in self.token_list:
            dispenser = TokenDispenser(host)
            if dispenser.email is None:
                logger.debug('Unable to obtain required information from {}', host)
                continue
            self.token = dispenser.token
            self.email = dispenser.email
            self.gsfid = self.api.checkin(self.email, self.token)
            if not self.connect_token():
                logger.warning(f"Unable to login.  Skipping {host}")
                continue
            logger.debug(f"Successfully logged into {host}")
            self.write_cached_token(args, host, self.token, self.gsfid, self.email)
            return True
        return False

    def generate_token_list(self, args) -> List[str]:
        token_list = []
        token_files = [args.token_dispenser_user, args.token_dispenser]
        for token_file in token_files:
            if token_file is None:
                continue
            try:
                with open(token_file, 'r') as fh:
                    for host in fh.readlines():
                        if not host.strip():
                            continue
                        if host.strip() not in fh:
                            token_list.append(host.strip())
            except FileNotFoundError:
                logger.debug(f"Unable to find token file {token_file}")
        logger.debug(f"Token Dispensers: {token_list}")
        return token_list

    def retrieve_token(self, host, args, force_new=False):
        self.token, self.gsfid, self.email = self.get_cached_token(host, args)
        if (self.token is not None and not force_new):
            logger.info("Using cached token.")
            self.gsfid = self.api.checkin(self.email, self.token)
            return True

    def write_cached_token(self, args, host, token, gsfid, email):
        parsed_name = self.cache_get_name(host)
        cache_filepath = '{}/{}'.format(args.temp_path, parsed_name)
        with open(cache_filepath, 'w+') as cache:
            data = {
                'email': email,
                'token': token,
                'gsfid': gsfid
            }
            json.dump(data, cache)
