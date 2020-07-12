import os
import sys
import time
from mapadroid.utils.functions import pngtojpg
from mapadroid.utils.logging import get_logger, LoggerEnums, get_origin_logger


logger = get_logger(LoggerEnums.utils)


class ADBConnect(object):
    def __init__(self, args):
        self._args = args
        self._useadb = args.use_adb
        self._client = None
        if self._useadb:
            try:
                from ppadb.client import Client as AdbClient
            except ImportError:
                try:
                    from adb.client import Client as AdbClient
                except ImportError:
                    pass
            self.check_adblib = 'adb.client' in sys.modules or 'ppadb.client' in sys.modules
            if not self.check_adblib:
                logger.warning("Could not find pure-python-adb library.  If you are not using ADB you can ignore this")
                self._useadb = False
            else:
                self._client = AdbClient(
                    host=self._args.adb_server_ip, port=self._args.adb_server_port)

    def check_adb_status(self, adb):
        if not self._useadb:
            return None
        try:
            if self._client.device(adb) is not None:
                self._client.device(adb).shell('echo checkadb')
                return True
        except RuntimeError:
            logger.exception('MADmin: Exception occurred while checking adb status ({}).', adb)
        return None

    def return_adb_devices(self):
        if not self._useadb:
            return []
        try:
            return self._client.devices()
        except Exception as e:
            logger.exception('MADmin: Exception occurred while getting adb clients: {}.', e)
        return []

    def send_shell_command(self, adb, origin, command):
        origin_logger = get_origin_logger(logger, origin=origin)
        try:
            device = self._client.device(adb)
            if device is not None:
                origin_logger.info('MADmin: Using ADB shell command')
                device.shell(command)
                return True
        except Exception as e:
            origin_logger.exception('MADmin: Exception occurred while sending shell command: {}.', e)
        return False

    def make_screenshot(self, adb, origin, extenstion):
        origin_logger = get_origin_logger(logger, origin=origin)
        try:
            device = self._client.device(adb)
            if device is not None:
                origin_logger.info('MADmin: Using ADB')
                result = device.screencap()
                # TODO: adjust with devicesettings
                with open(os.path.join(self._args.temp_path, 'screenshot_%s.png' % str(origin)), "wb") as fp:
                    fp.write(result)
                if extenstion == "jpg":
                    pngtojpg(os.path.join(self._args.temp_path, 'screenshot_%s.png' % str(origin)))
                return True
        except Exception as e:
            origin_logger.exception('MADmin: Exception occurred while making screenshot: {}.', e)
        return False

    def make_screenclick(self, adb, origin, x, y):
        origin_logger = get_origin_logger(logger, origin=origin)
        try:
            device = self._client.device(adb)
            if device is not None:
                device.shell("input tap " + str(x) + " " + str(y))
                origin_logger.info('MADMin ADB Click x:{} y:{}', x, y)
                time.sleep(1)
                return True
        except Exception as e:
            origin_logger.exception('MADmin: Exception occurred while making screenclick: {}.', e)
        return False

    def make_screenswipe(self, adb, origin, x, y, xe, ye):
        origin_logger = get_origin_logger(logger, origin=origin)
        try:
            device = self._client.device(adb)
            if device is not None:
                device.shell("input swipe " + str(x) + " " +
                             str(y) + " " + str(xe) + " " + str(ye) + " 100")
                origin_logger.info('MADMin ADB Swipe x:{} y:{} xe:{} ye:{}', x, y, xe, ye)
                time.sleep(1)
                return True
        except Exception as e:
            origin_logger.exception('MADmin: Exception occurred while making screenswipe: {}.', e)
        return False

    def push_file(self, adb, origin, filename):
        origin_logger = get_origin_logger(logger, origin=origin)
        try:
            device = self._client.device(adb)
            if device is not None:
                device.shell("adb push  " + str(filename) + " /sdcard/Download")
                origin_logger.info('MADMin ADB Push File {}', filename)
                time.sleep(1)
                return True
        except Exception as e:
            origin_logger.exception('MADmin: Exception occurred while pushing file: {}.', e)
        return False
