import os
import time
import re

import xml.etree.ElementTree as ET
from utils.logging import logger
from utils.MappingManager import MappingManager
from typing import Optional, List
from utils.collections import Login_PTC, Login_GGL
from enum import Enum
import numpy as np
from utils.madGlobals import ScreenshotType
from PIL import Image
import gc

class ScreenType(Enum):
    UNDEFINED = -1
    RETURNING = 2
    LOGINSELECT = 3
    PTC = 4
    WRONG = 7
    BIRTHDATE = 1
    FAILURE = 5
    RETRY = 6
    GAMEDATA = 8
    POGO = 99
    GGL = 10
    PERMISSION = 11
    MARKETING = 12
    CONSENT = 13
    SN = 14
    UPDATE = 15
    QUEST = 20
    ERROR = 100
    BLACK = 110
    CLOSE = 500
    DISABLED = 999

class LoginType(Enum):
    UNKNOWN = -1
    google = 1
    ptc = 2


class WordToScreenMatching(object):
    def __init__(self, communicator, pogoWindowManager, id, resocalc, mapping_mananger: MappingManager, args):
        self._id = id
        self._applicationArgs = args
        self._mapping_manager = mapping_mananger
        self._ratio: float = 0.0

        self._logintype: LoginType = -1
        self._PTC_accounts: List[Login_PTC] = []
        self._GGL_accounts: List[Login_GGL] = []
        self._accountcount: int = 0
        self._accountindex: int = self.get_devicesettings_value('accountindex', 0)
        self._screenshot_y_offset: int = self.get_devicesettings_value('screenshot_y_offset', 0)
        self._nextscreen: ScreenType = ScreenType.UNDEFINED

        self._pogoWindowManager = pogoWindowManager
        self._communicator = communicator
        self._resocalc = resocalc
        logger.info("Starting Screendetector")
        self._width: int = 0
        self._height: int = 0
        self.get_login_accounts()

    def get_login_accounts(self):
        self._logintype = LoginType[self.get_devicesettings_value('logintype', 'google')]
        logger.info("Set logintype: {}".format(self._logintype))
        if self._logintype == LoginType.ptc:
            temp_accounts = self.get_devicesettings_value('ptc_login', False)
            if not temp_accounts:
                logger.warning('No PTC Accounts are set - hope we are login and never logout!')
                self._accountcount = 0
                return

            temp_accounts = temp_accounts.replace(' ', '').split('|')
            for account in temp_accounts:
                ptc_temp = account.split(',')
                if 2 < len(ptc_temp) > 2:
                    logger.warning('Cannot use this account (Wrong format!): {}'.format(str(account)))
                username = ptc_temp[0]
                password = ptc_temp[1]
                self._PTC_accounts.append(Login_PTC(username, password))
            self._accountcount = len(self._PTC_accounts)
        else:
            temp_accounts = self.get_devicesettings_value('ggl_login_mail', '@gmail.com')
            if not temp_accounts:
                logger.warning('No GGL Accounts are set - using first @gmail.com Account')
            temp_accounts = temp_accounts.replace(' ', '').split('|')

            for account in temp_accounts:
                self._GGL_accounts.append(Login_GGL(account))
            self._accountcount = len(self._GGL_accounts)

        logger.info('Added {} account(s) to memory'.format(str(self._accountcount)))
        return

    def get_next_account(self):
        if self._accountcount == 0:
            logger.info('Cannot return new account - no one is set')
            return None
        if self._accountindex <= self._accountcount - 1:
            logger.info('Request next Account - Using Nr. {}'.format(self._accountindex+1))
            self._accountindex += 1
        elif self._accountindex > self._accountcount - 1:
            logger.info('Request next Account - Restarting with Nr. 1')
            self._accountindex = 0

        self.set_devicesettings_value('accountindex', self._accountindex)

        if self._logintype == LoginType.ptc:
            logger.info('Using PTC Account: {}'.format
                        (self.censor_account(self._PTC_accounts[self._accountindex-1].username, isPTC=True)))
            return self._PTC_accounts[self._accountindex-1]
        else:
            logger.info('Using GGL Account: {}'.format
                        (self.censor_account(self._GGL_accounts[self._accountindex-1].username)))
            return self._GGL_accounts[self._accountindex-1]

    def return_memory_account_count(self):
        return self._accountcount

    def check_lines(self, lines, height):
        temp_lines = []
        sort_lines = []
        old_y1 = 0
        index = 0

        for line in lines:
            for x1, y1, x2, y2 in line:
                temp_lines.append([y1, y2, x1, x2])

        temp_lines = np.array(temp_lines)
        sort_arr = (temp_lines[temp_lines[:, 0].argsort()])

        button_value = height / 40

        for line in sort_arr:
            if int(old_y1 + int(button_value)) < int(line[0]):
                if int(line[0]) == int(line[1]):
                    sort_lines.append([line[2], line[0], line[3], line[1]])
                    old_y1 = line[0]
            index += 1

        return np.asarray(sort_lines, dtype=np.int32)

    def matchScreen(self):
        globaldict: dict = {}
        pogoTopmost = self._communicator.isPogoTopmost()
        screenpath = self.get_screenshot_path()
        topmostapp = self._communicator.topmostApp()
        if not topmostapp:
            return ScreenType.ERROR

        returntype: ScreenType = -1

        if "AccountPickerActivity" in topmostapp or 'SignInActivity' in topmostapp:
            returntype = 10
        elif "GrantPermissionsActivity" in topmostapp:
            returntype = 11
        elif "ConsentActivity" in topmostapp:
            returntype = 13
        elif not pogoTopmost:
            return ScreenType.CLOSE
        elif self._nextscreen != ScreenType.UNDEFINED:
            returntype = ScreenType(self._nextscreen)
        elif not self.get_devicesettings_value('screendetection', False):
            logger.info('No more screen detection - disabled ...')
            return ScreenType.DISABLED
        else:
            if not self._takeScreenshot(delayBefore=self.get_devicesettings_value("post_screenshot_delay", 1),
                                                delayAfter=2):
                logger.error("_check_windows: Failed getting screenshot")
                return ScreenType.ERROR

            returntype, globaldict, self._width, self._height, diff = \
                self._pogoWindowManager.screendetection_get_type(screenpath, self._id)

            self._ratio = self._height / self._width

            logger.debug("Screenratio of origin {}: {}".format(str(self._id), str(self._ratio)))

            if 'text' not in globaldict:
                logger.error('Error while text detection')
                return ScreenType.ERROR

        if ScreenType(returntype) != ScreenType.UNDEFINED:
            logger.info("Processing Screen: {}", str(ScreenType(returntype)))

        if ScreenType(returntype) == ScreenType.GGL:
            self._nextscreen = ScreenType.UNDEFINED

            if self._logintype == LoginType.ptc:
                logger.warning('Really dont know how i get there ... using first @ggl address ... :)')
                username = self.get_devicesettings_value('ggl_login_mail', '@gmail.com')
            else:
                ggl_login = self.get_next_account()
                username = ggl_login.username

            if self.parse_ggl(self._communicator.uiautomator(), username):
                logger.info("Sleeping 50 seconds - please wait!!!!")
                time.sleep(50)

                return ScreenType.GGL
            return ScreenType.ERROR

        elif ScreenType(returntype) == ScreenType.PERMISSION:
            self._nextscreen = ScreenType.UNDEFINED
            if self.parse_permission(self._communicator.uiautomator()):
                time.sleep(2)
                return ScreenType.PERMISSION
            time.sleep(2)
            return ScreenType.ERROR

        elif ScreenType(returntype) == ScreenType.CONSENT:
            self._nextscreen = ScreenType.UNDEFINED
            return ScreenType.CONSENT

        elif ScreenType(returntype) == ScreenType.UPDATE:
            self._nextscreen = ScreenType.UNDEFINED
            return ScreenType.UPDATE

        elif ScreenType(returntype) == ScreenType.SN:
            self._nextscreen = ScreenType.UNDEFINED
            return ScreenType.SN

        elif ScreenType(returntype) == ScreenType.GAMEDATA:
            self._nextscreen = ScreenType.UNDEFINED
            return ScreenType.GAMEDATA

        elif ScreenType(returntype) == ScreenType.MARKETING:
            self._nextscreen = ScreenType.POGO
            click_text = 'ERLAUBEN,ALLOW,AUTORISER'
            n_boxes = len(globaldict['level'])
            for i in range(n_boxes):
                if any(elem.lower() in (globaldict['text'][i].lower()) for elem in click_text.split(",")):
                    (x, y, w, h) = (globaldict['left'][i], globaldict['top'][i],
                                    globaldict['width'][i], globaldict['height'][i])
                    click_x, click_y = (x + w / 2) / diff, (y + h / 2) / diff
                    logger.debug('Click ' + str(click_x) + ' / ' + str(click_y))
                    self._communicator.click(click_x, click_y)
                    time.sleep(2)

            return ScreenType.MARKETING

        elif ScreenType(returntype) == ScreenType.BIRTHDATE:
            self._nextscreen = ScreenType.UNDEFINED
            click_x = (self._width / 2) + (self._width / 4)
            click_y = (self._height / 1.69) + self._screenshot_y_offset
            logger.debug('Click ' + str(click_x) + ' / ' + str(click_y))
            self._communicator.click(click_x, click_y)
            self._communicator.touchandhold(click_x, click_y, click_x, click_y - (self._height / 2), 200)
            time.sleep(1)
            self._communicator.click(click_x, click_y)
            time.sleep(1)
            click_x = self._width / 2
            click_y = click_y + (self._height / 8.53)
            self._communicator.click(click_x, click_y)
            time.sleep(1)
            return ScreenType.BIRTHDATE

        elif ScreenType(returntype) == ScreenType.RETURNING:
            self._nextscreen = ScreenType.UNDEFINED
            self._pogoWindowManager.look_for_button(screenpath, 2.20, 3.01, self._communicator, upper=True)
            time.sleep(2)
            return ScreenType.RETURNING

        elif ScreenType(returntype) == ScreenType.WRONG:
            self._nextscreen = ScreenType.UNDEFINED
            self._pogoWindowManager.look_for_button(screenpath, 2.20, 3.01, self._communicator, upper=True)
            time.sleep(2)
            return ScreenType.ERROR

        elif ScreenType(returntype) == ScreenType.LOGINSELECT:
            temp_dict: dict = {}
            n_boxes = len(globaldict['level'])
            for i in range(n_boxes):
                if 'Facebook' in (globaldict['text'][i]): temp_dict['Facebook'] = globaldict['top'][i] / diff
                if 'CLUB' in (globaldict['text'][i]): temp_dict['CLUB'] = globaldict['top'][i] / diff
                # french ...
                if 'DRESSEURS' in (globaldict['text'][i]): temp_dict['CLUB'] = globaldict['top'][i] / diff

                if self.get_devicesettings_value('logintype', 'google') == 'ptc':
                    self._nextscreen = ScreenType.PTC
                    if 'CLUB' in (globaldict['text'][i]):
                        (x, y, w, h) = (globaldict['left'][i], globaldict['top'][i],
                                        globaldict['width'][i], globaldict['height'][i])
                        click_x, click_y = (x + w / 2) / diff, (y + h / 2) / diff
                        logger.debug('Click ' + str(click_x) + ' / ' + str(click_y))
                        self._communicator.click(click_x, click_y)
                        time.sleep(5)
                        return ScreenType.LOGINSELECT

                else:
                    self._nextscreen = ScreenType.UNDEFINED
                    if 'Google' in (globaldict['text'][i]):
                        (x, y, w, h) = (globaldict['left'][i], globaldict['top'][i],
                                        globaldict['width'][i], globaldict['height'][i])
                        click_x, click_y = (x + w / 2) / diff, (y + h / 2) / diff
                        logger.debug('Click ' + str(click_x) + ' / ' + str(click_y))
                        self._communicator.click(click_x, click_y)
                        time.sleep(5)
                        return ScreenType.LOGINSELECT

                    # alternative select
                    if 'Facebook' in temp_dict and 'TRAINER' in temp_dict:
                        click_x = self._width / 2
                        click_y = (temp_dict['Facebook'] + ((temp_dict['TRAINER'] - temp_dict['Facebook']) / 2))
                        logger.debug('Click ' + str(click_x) + ' / ' + str(click_y))
                        self._communicator.click(click_x, click_y)
                        time.sleep(5)
                        return ScreenType.LOGINSELECT

                    # alternative select
                    if 'Facebook' in temp_dict:
                        click_x = self._width / 2
                        click_y = (temp_dict['Facebook'] + self._height / 10.11)
                        logger.debug('Click ' + str(click_x) + ' / ' + str(click_y))
                        self._communicator.click(click_x, click_y)
                        time.sleep(5)
                        return ScreenType.LOGINSELECT

                    # alternative select
                    if 'CLUB' in temp_dict:
                        click_x = self._width / 2
                        click_y = (temp_dict['CLUB'] - self._height / 10.11)
                        logger.debug('Click ' + str(click_x) + ' / ' + str(click_y))
                        self._communicator.click(click_x, click_y)
                        time.sleep(5)
                        return ScreenType.LOGINSELECT

        elif ScreenType(returntype) == ScreenType.PTC:
            self._nextscreen = ScreenType.UNDEFINED
            ptc = self.get_next_account()
            if not ptc:
                logger.error('No PTC Username and Password is set')
                return ScreenType.ERROR

            if float(self._ratio) >= 2:
                username_y = self._height / 2.5 + self._screenshot_y_offset
                password_y = self._height / 2.105 + self._screenshot_y_offset
                button_y = self._height / 1.7777 + self._screenshot_y_offset
            elif float(self._ratio) >= 1.7:
                username_y = self._height / 2.224797219003476 + self._screenshot_y_offset
                password_y = self._height / 1.875 + self._screenshot_y_offset
                button_y = self._height / 1.58285243198681 + self._screenshot_y_offset
            elif float(self._ratio) < 1.7:
                username_y = self._height / 2.224797219003476 + self._screenshot_y_offset
                password_y = self._height / 1.875 + self._screenshot_y_offset
                button_y = self._height / 1.58285243198681 + self._screenshot_y_offset

            # username
            self._communicator.click(self._width / 2, username_y)
            time.sleep(.5)
            self._communicator.sendText(ptc.username)
            self._communicator.click(100, 100)
            time.sleep(2)

            # password
            self._communicator.click(self._width / 2, password_y)
            time.sleep(.5)
            self._communicator.sendText(ptc.password)
            self._communicator.click(100, 100)
            time.sleep(2)

            # button
            self._communicator.click(self._width / 2, button_y)
            logger.info("Sleeping 50 seconds - please wait!!!!")
            time.sleep(50)
            return ScreenType.PTC

        elif ScreenType(returntype) == ScreenType.FAILURE:
            self._nextscreen = ScreenType.UNDEFINED
            self._pogoWindowManager.look_for_button(screenpath, 2.20, 3.01, self._communicator)
            time.sleep(2)
            return ScreenType.ERROR

        elif ScreenType(returntype) == ScreenType.RETRY:
            self._nextscreen = ScreenType.UNDEFINED
            click_text = 'DIFFERENT,AUTRE,AUTORISER,ANDERES,KONTO,ACCOUNT'
            n_boxes = len(globaldict['level'])
            for i in range(n_boxes):
                if any(elem in (globaldict['text'][i]) for elem in click_text.split(",")):
                    (x, y, w, h) = (globaldict['left'][i], globaldict['top'][i],
                                    globaldict['width'][i], globaldict['height'][i])
                    click_x, click_y = (x + w / 2) / diff, (y + h / 2) / diff
                    logger.debug('Click ' + str(click_x) + ' / ' + str(click_y))
                    self._communicator.click(click_x, click_y)
                    time.sleep(2)
            return ScreenType.RETRY

        else:

            backgroundcolor = self._pogoWindowManager.most_frequent_colour(screenpath, self._id)

            if backgroundcolor is not None and (
                    backgroundcolor[0] == 0 and
                    backgroundcolor[1] == 0 and
                    backgroundcolor[2] == 0):
                # Background is black - Loading ...
                return ScreenType.BLACK

            return ScreenType.POGO

    def checkQuest(self, screenpath):

        with Image.open(screenpath) as frame:
            frame = frame.convert('LA')

            globaldict = self._pogoWindowManager.get_screen_text(frame, self._id)
            click_text = 'FIELD,SPECIAL,FELD,SPEZIAL,SPECIALES,TERRAIN'
            n_boxes = len(globaldict['level'])
            for i in range(n_boxes):
                if any(elem in (globaldict['text'][i]) for elem in click_text.split(",")):
                    logger.info('Found research menu')
                    self._communicator.click(100, 100)
                    return ScreenType.QUEST

            logger.info('Listening to Dr. blabla - please wait')

            self._communicator.backButton()
            time.sleep(3)
            return ScreenType.UNDEFINED

    def parse_permission(self, xml):
        if xml is None:
            logger.warning('Something wrong with processing - getting None Type from Websocket...')
            return False
        click_text = ('ZULASSEN', 'ALLOW', 'AUTORISER')
        try:
            parser = ET.XMLParser(encoding="utf-8")
            xmlroot = ET.fromstring(xml, parser=parser)
            bounds: str = ""
            for item in xmlroot.iter('node'):
                if str(item.attrib['text']).upper() in click_text:
                    logger.debug("Found text {}", str(item.attrib['text']))
                    bounds = item.attrib['bounds']
                    logger.debug("Bounds {}", str(item.attrib['bounds']))

                    match = re.search(r'^\[(\d+),(\d+)\]\[(\d+),(\d+)\]$', bounds)

                    click_x = int(match.group(1)) + ((int(match.group(3)) - int(match.group(1)))/2)
                    click_y = int(match.group(2)) + ((int(match.group(4)) - int(match.group(2)))/2)
                    logger.debug('Click ' + str(click_x) + ' / ' + str(click_y))
                    self._communicator.click(click_x, click_y)
                    time.sleep(2)
                    return True
        except Exception as e:
            logger.error('Something wrong while parsing xml: {}'.format(str(e)))
            return False

        time.sleep(2)
        logger.warning('Dont find any button...')
        return False

    def parse_ggl(self, xml, mail: str):
        if xml is None:
            logger.warning('Something wrong with processing - getting None Type from Websocket...')
            return False
        try:
            parser = ET.XMLParser(encoding="utf-8")
            xmlroot = ET.fromstring(xml, parser=parser)
            for item in xmlroot.iter('node'):
                if mail.lower() in str(item.attrib['text']).lower():
                    logger.info("Found mail {}", self.censor_account(str(item.attrib['text'])))
                    bounds = item.attrib['bounds']
                    logger.debug("Bounds {}", str(item.attrib['bounds']))
                    match = re.search(r'^\[(\d+),(\d+)\]\[(\d+),(\d+)\]$', bounds)
                    click_x = int(match.group(1)) + ((int(match.group(3)) - int(match.group(1))) / 2)
                    click_y = int(match.group(2)) + ((int(match.group(4)) - int(match.group(2))) / 2)
                    logger.debug('Click ' + str(click_x) + ' / ' + str(click_y))
                    self._communicator.click(click_x, click_y)
                    time.sleep(2)
                    return True
        except Exception as e:
            logger.error('Something wrong while parsing xml: {}'.format(str(e)))
            return False

        time.sleep(2)
        logger.warning('Dont find any mailaddress...')
        return False

    def set_devicesettings_value(self, key: str, value):
        self._mapping_manager.set_devicesetting_value_of(self._id, key, value)

    def get_devicesettings_value(self, key: str, default_value: object = None):
        logger.debug2("Fetching devicemappings of {}".format(self._id))
        try:
            devicemappings: Optional[dict] = self._mapping_manager.get_devicemappings_of(self._id)
        except (EOFError, FileNotFoundError) as e:
            logger.warning("Failed fetching devicemappings in worker {} with description: {}. Stopping worker"
                           .format(str(self._id), str(e)))
            return None
        if devicemappings is None:
            return default_value
        return devicemappings.get("settings", {}).get(key, default_value)
    
    def censor_account(self, emailaddress, isPTC=False):
        # PTC account
        if isPTC:
            return (emailaddress[0:2]+"***"+emailaddress[-2:])
        # GGL - make sure we have @ there.
        # If not it could be wrong match, so returning original
        if '@' in emailaddress:
            d = emailaddress.split("@", 1)
            # long local-part, censor middle part only
            if len(d[0]) > 6:
                return (d[0][0:2]+"***"+d[0][-2:]+"@"+d[1])
            # domain only, just return
            elif len(d[0]) == 0:
                return (emailaddress)
            # local-part is short, asterix for each char
            else:
                return ("*"*len(d[0])+"@"+d[1])
        return emailaddress

    def get_screenshot_path(self, fileaddon: bool = False) -> str:
        screenshot_ending: str = ".jpg"
        addon: str = ""
        if self.get_devicesettings_value("screenshot_type", "jpeg") == "png":
            screenshot_ending = ".png"

        if fileaddon:
            addon: str = "_" + str(time.time())

        screenshot_filename = "screenshot_{}{}{}".format(str(self._id), str(addon), screenshot_ending)

        if fileaddon:
            logger.info("Creating debugscreen: {}".format(screenshot_filename))

        return os.path.join(
                self._applicationArgs.temp_path, screenshot_filename)

    def _takeScreenshot(self, delayAfter=0.0, delayBefore=0.0, errorscreen: bool = False):
        logger.debug("Taking screenshot...")
        time.sleep(delayBefore)

        # TODO: area settings for jpg/png and quality?
        screenshot_type: ScreenshotType = ScreenshotType.JPEG
        if self.get_devicesettings_value("screenshot_type", "jpeg") == "png":
            screenshot_type = ScreenshotType.PNG

        screenshot_quality: int = 80

        take_screenshot = self._communicator.get_screenshot(self.get_screenshot_path(fileaddon=errorscreen),
                                                            screenshot_quality, screenshot_type)

        if not take_screenshot:
            logger.error("takeScreenshot: Failed retrieving screenshot")
            logger.debug("Failed retrieving screenshot")
            return False
        else:
            logger.debug("Success retrieving screenshot")
            self._lastScreenshotTaken = time.time()
            time.sleep(delayAfter)
            return True




