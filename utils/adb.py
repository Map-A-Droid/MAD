from adb.client import Client as AdbClient
from loguru import logger
import os
import time
from utils.walkerArgs import parseArgs

log = logger
args = parseArgs()
client = AdbClient(host=args.adb_server_ip, port=args.adb_server_port)

def check_adb_status(adb):
    if client.device(adb) is not None:
        return True
    return None


def return_adb_devices():
    return client.devices()


def send_shell_command(adb, origin, command):
    try:
        device = client.device(adb)
        if device is not None:
            logger.info('MADmin: Using ADB ({})', str(origin))
            device.shell(command)
            return True
    except Exception as e:
        logger.exception(
            'MADmin: Exception occurred while sending shell command ({}): {}.', str(origin), e)
    return False


def make_screenshot(adb, origin):
    try:
        device = client.device(adb)
        if device is not None:
            logger.info('MADmin: Using ADB ({})', str(origin))
            result = device.screencap()
            with open(os.path.join(args.temp_path, 'screenshot%s.png' % str(origin)), "wb") as fp:
                fp.write(result)
            return True
    except Exception as e:
        logger.exception(
            'MADmin: Exception occurred while making screenshot ({}): {}.', str(origin), e)
    return False


def make_screenclick(adb, origin, x, y):
    try:
        device = client.device(adb)
        if device is not None:
            device.shell("input tap " + str(x) + " " + str(y))
            logger.info('MADMin ADB Click x:{} y:{} ({})', str(x), str(y), str(origin))
            time.sleep(1)
            return True
    except Exception as e:
        logger.exception(
            'MADmin: Exception occurred while making screenclick ({}): {}.', str(origin), e)
    return False


def make_screenswipe(adb, origin, x, y, xe, ye):
    try:
        device = client.device(adb)
        if device is not None:
            device.shell("input swipe " + str(x) + " " + str(y) + " " + str(xe) + " " + str(ye) + " 3000")
            logger.info('MADMin ADB Swipe x:{} y:{} xe:{} ye:{}({})', str(x), str(y), str(xe), str(ye), str(origin))
            time.sleep(1)
            return True
    except Exception as e:
        logger.exception(
            'MADmin: Exception occurred while making screenswipe ({}): {}.', str(origin), e)
    return False


