import os
import sys
import time
from mapadroid.utils.functions import pngtojpg
from mapadroid.utils.logging import get_logger, LoggerEnums


log = get_logger(LoggerEnums.utils)


class ADBConnect(object):
    def __init__(self, args):
        self._args = args
        self._useadb = args.use_adb
        self._client = None
        if self._useadb:
            try:
                from adb.client import Client as AdbClient
            except ImportError:
                pass
            try:
                from ppadb.client import Client as AdbClient
            except ImportError:
                pass
            self.check_adblib = 'adb.client' in sys.modules or 'ppadb.client' in sys.modules
            if not self.check_adblib:
                logger.warning(
                    "Could not find pure-python-adb library - no support for ADB."
                    "If you have no idea what ADB is or not planning to use it - IGNORE :)"
                )
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
        except RuntimeError as e:
            logger.exception(
                'MADmin: Exception occurred while checking adb status ({}).', str(adb))
        return None

    def return_adb_devices(self):
        if not self._useadb:
            return []
        try:
            return self._client.devices()
        except Exception as e:
            logger.exception(
                'MADmin: Exception occurred while getting adb clients: {}.', e)
        return []

    def send_shell_command(self, adb, origin, command):
        try:
            device = self._client.device(adb)
            if device is not None:
                logger.info(
                    'MADmin: Using ADB shell command ({})', str(origin))
                device.shell(command)
                return True
        except Exception as e:
            logger.exception(
                'MADmin: Exception occurred while sending shell command ({}): {}.', str(origin), e)
        return False

    def make_screenshot(self, adb, origin, extenstion):
        try:
            device = self._client.device(adb)
            if device is not None:
                logger.info('MADmin: Using ADB ({})', str(origin))
                result = device.screencap()
                # TODO: adjust with devicesettings
                with open(os.path.join(self._args.temp_path, 'screenshot_%s.png' % str(origin)), "wb") as fp:
                    fp.write(result)
                if extenstion == "jpg":
                    pngtojpg(os.path.join(self._args.temp_path, 'screenshot_%s.png' % str(origin)))
                return True
        except Exception as e:
            logger.exception(
                'MADmin: Exception occurred while making screenshot ({}): {}.', str(origin), e)
        return False

    def make_screenclick(self, adb, origin, x, y):
        try:
            device = self._client.device(adb)
            if device is not None:
                device.shell("input tap " + str(x) + " " + str(y))
                logger.info('MADMin ADB Click x:{} y:{} ({})',
                            str(x), str(y), str(origin))
                time.sleep(1)
                return True
        except Exception as e:
            logger.exception(
                'MADmin: Exception occurred while making screenclick ({}): {}.', str(origin), e)
        return False

    def make_screenswipe(self, adb, origin, x, y, xe, ye):
        try:
            device = self._client.device(adb)
            if device is not None:
                device.shell("input swipe " + str(x) + " " +
                             str(y) + " " + str(xe) + " " + str(ye) + " 100")
                logger.info('MADMin ADB Swipe x:{} y:{} xe:{} ye:{}({})', str(
                    x), str(y), str(xe), str(ye), str(origin))
                time.sleep(1)
                return True
        except Exception as e:
            logger.exception(
                'MADmin: Exception occurred while making screenswipe ({}): {}.', str(origin), e)
        return False

    def push_file(self, adb, origin, filename):
        try:
            device = self._client.device(adb)
            if device is not None:
                device.shell("adb push  " + str(filename) + " /sdcard/Download")
                logger.info('MADMin ADB Push File {} to {})', str(filename), str(origin))
                time.sleep(1)
                return True
        except Exception as e:
            logger.exception(
                'MADmin: Exception occurred while making screenswipe ({}): {}.', str(origin), e)
        return False
