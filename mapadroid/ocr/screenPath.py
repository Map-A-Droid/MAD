import os
import re
import time
import xml.etree.ElementTree as ET
from enum import Enum
from typing import Optional, List, Tuple
import numpy as np
from mapadroid.ocr.screen_type import ScreenType
from mapadroid.utils import MappingManager
from mapadroid.utils.collections import Login_PTC, Login_GGL
from mapadroid.utils.madGlobals import ScreenshotType
from mapadroid.utils.logging import get_logger, LoggerEnums, get_origin_logger


logger = get_logger(LoggerEnums.ocr)


class LoginType(Enum):
    UNKNOWN = -1
    google = 1
    ptc = 2


class WordToScreenMatching(object):
    def __init__(self, communicator, pogoWindowManager, origin, resocalc, mapping_mananger: MappingManager, args):
        self._id = origin
        self._logger = get_origin_logger(logger, origin=origin)
        self._applicationArgs = args
        self._mapping_manager = mapping_mananger
        self._ratio: float = 0.0

        self._logintype: LoginType = LoginType.UNKNOWN
        self._PTC_accounts: List[Login_PTC] = []
        self._GGL_accounts: List[Login_GGL] = []
        self._accountcount: int = 0
        self._accountindex: int = self.get_devicesettings_value('accountindex', 0)
        self._screenshot_y_offset: int = self.get_devicesettings_value('screenshot_y_offset', 0)
        self._nextscreen: ScreenType = ScreenType.UNDEFINED

        self._pogoWindowManager = pogoWindowManager
        self._communicator = communicator
        self._resocalc = resocalc
        self._logger.info("Starting Screendetector")
        self._width: int = 0
        self._height: int = 0
        self.get_login_accounts()

    def get_login_accounts(self):
        self._logintype = LoginType[self.get_devicesettings_value('logintype', 'google')]
        self._logger.info("Set logintype: {}", self._logintype)
        if self._logintype == LoginType.ptc:
            temp_accounts = self.get_devicesettings_value('ptc_login', False)
            if not temp_accounts:
                self._logger.warning('No PTC Accounts are set - hope we are login and never logout!')
                self._accountcount = 0
                return

            temp_accounts = temp_accounts.replace(' ', '').split('|')
            for account in temp_accounts:
                ptc_temp = account.split(',')
                if len(ptc_temp) != 2:
                    self._logger.warning('Cannot use this account (Wrong format!): {}', account)
                    continue
                username = ptc_temp[0]
                password = ptc_temp[1]
                self._PTC_accounts.append(Login_PTC(username, password))
            self._accountcount = len(self._PTC_accounts)
        else:
            temp_accounts = self.get_devicesettings_value('ggl_login_mail', '@gmail.com')
            if not temp_accounts:
                self._logger.warning('No GGL Accounts are set - using first @gmail.com Account')
            temp_accounts = temp_accounts.replace(' ', '').split('|')

            for account in temp_accounts:
                self._GGL_accounts.append(Login_GGL(account))
            self._accountcount = len(self._GGL_accounts)

        self._logger.info('Added {} account(s) to memory', self._accountcount)
        return

    def get_next_account(self):
        if self._accountcount == 0:
            self._logger.info('Cannot return new account - no one is set')
            return None
        if self._accountindex <= self._accountcount - 1:
            self._logger.info('Request next Account - Using Nr. {}', self._accountindex + 1)
            self._accountindex += 1
        elif self._accountindex > self._accountcount - 1:
            self._logger.info('Request next Account - Restarting with Nr. 1')
            self._accountindex = 0

        self.set_devicesettings_value('accountindex', self._accountindex)

        if self._logintype == LoginType.ptc:
            self._logger.info('Using PTC Account: {}',
                              self.censor_account(self._PTC_accounts[self._accountindex - 1].username, isPTC=True))
            return self._PTC_accounts[self._accountindex - 1]
        else:
            self._logger.info('Using GGL Account: {}',
                              self.censor_account(self._GGL_accounts[self._accountindex - 1].username))
            return self._GGL_accounts[self._accountindex - 1]

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

    def __evaluate_topmost_app(self, topmost_app: str) -> Tuple[ScreenType, dict, int]:
        returntype: ScreenType = ScreenType.UNDEFINED
        global_dict: dict = {}
        diff = 1
        if "AccountPickerActivity" in topmost_app or 'SignInActivity' in topmost_app:
            return ScreenType.GGL, global_dict, diff
        elif "GrantPermissionsActivity" in topmost_app:
            return ScreenType.PERMISSION, global_dict, diff
        elif "GrantCredentialsWithAclNoTouchActivity" in topmost_app or "GrantCredentials" in topmost_app:
            return ScreenType.CREDENTIALS, global_dict, diff
        elif "ConsentActivity" in topmost_app:
            return ScreenType.CONSENT, global_dict, diff
        elif "com.nianticlabs.pokemongo" not in topmost_app:
            self._logger.warning("PoGo is not opened! Current topmost app: {}", topmost_app)
            return ScreenType.CLOSE, global_dict, diff
        elif self._nextscreen != ScreenType.UNDEFINED:
            # TODO: how can the nextscreen be known in the current? o.O
            return self._nextscreen, global_dict, diff
        elif not self.get_devicesettings_value('screendetection', False):
            self._logger.info('Screen detection is disabled')
            return ScreenType.DISABLED, global_dict, diff
        else:
            if not self._takeScreenshot(delayBefore=self.get_devicesettings_value("post_screenshot_delay", 1),
                                        delayAfter=2):
                self._logger.error("_check_windows: Failed getting screenshot")
                return ScreenType.ERROR, global_dict, diff

            screenpath = self.get_screenshot_path()

            result = self._pogoWindowManager.screendetection_get_type_by_screen_analysis(screenpath, self.origin)
            if result is None:
                self._logger.error("Failed analyzing screen")
                return ScreenType.ERROR, global_dict, diff
            else:
                returntype, global_dict, self._width, self._height, diff = result
            if not global_dict:
                self._nextscreen = ScreenType.UNDEFINED
                self._logger.warning('Could not understand any text on screen - starting next round...')
                return ScreenType.ERROR, global_dict, diff

            self._ratio = self._height / self._width

            self._logger.debug("Screenratio: {}", self._ratio)

            if 'text' not in global_dict:
                self._logger.error('Error while text detection')
                return ScreenType.ERROR, global_dict, diff
            elif returntype == ScreenType.UNDEFINED and "com.nianticlabs.pokemongo" in topmost_app:
                return ScreenType.POGO, global_dict, diff

        return returntype, global_dict, diff

    def __handle_login_screen(self, global_dict: dict, diff: int) -> None:
        temp_dict: dict = {}
        n_boxes = len(global_dict['level'])
        self._logger.debug("Selecting login with: {}", global_dict)
        for i in range(n_boxes):
            if 'Facebook' in (global_dict['text'][i]):
                temp_dict['Facebook'] = global_dict['top'][i] / diff
            if 'CLUB' in (global_dict['text'][i]):
                temp_dict['CLUB'] = global_dict['top'][i] / diff
            # french ...
            if 'DRESSEURS' in (global_dict['text'][i]):
                temp_dict['CLUB'] = global_dict['top'][i] / diff
            if 'Google' in (global_dict['text'][i]):
                temp_dict['Google'] = global_dict['top'][i] / diff

            if self.get_devicesettings_value('logintype', 'google') == 'ptc':
                self._nextscreen = ScreenType.PTC
                if 'CLUB' in (global_dict['text'][i]):
                    self._click_center_button(diff, global_dict, i)
                    time.sleep(5)
                    return

                # alternative select - calculate down from Facebook button
                elif 'Facebook' in temp_dict:
                    click_x = self._width / 2
                    click_y = (temp_dict['Facebook'] + 2 * self._height / 10.11)
                    self._communicator.click(click_x, click_y)
                    time.sleep(5)
                    return

                # alternative select - calculate down from Google button
                elif 'Google' in temp_dict:
                    click_x = self._width / 2
                    click_y = (temp_dict['Google'] + self._height / 10.11)
                    self._communicator.click(click_x, click_y)
                    time.sleep(5)
                    return

            else:
                self._nextscreen = ScreenType.UNDEFINED
                if 'Google' in (global_dict['text'][i]):
                    self._click_center_button(diff, global_dict, i)
                    time.sleep(5)
                    return

                # alternative select
                elif 'Facebook' in temp_dict and 'CLUB' in temp_dict:
                    click_x = self._width / 2
                    click_y = (temp_dict['Facebook'] + ((temp_dict['CLUB'] - temp_dict['Facebook']) / 2))
                    self._communicator.click(click_x, click_y)
                    time.sleep(5)
                    return

                # alternative select
                elif 'Facebook' in temp_dict:
                    click_x = self._width / 2
                    click_y = (temp_dict['Facebook'] + self._height / 10.11)
                    self._communicator.click(click_x, click_y)
                    time.sleep(5)
                    return

                # alternative select
                elif 'CLUB' in temp_dict:
                    click_x = self._width / 2
                    click_y = (temp_dict['CLUB'] - self._height / 10.11)
                    self._communicator.click(click_x, click_y)
                    time.sleep(5)
                    return

    def _click_center_button(self, diff, global_dict, i) -> None:
        (x, y, w, h) = (global_dict['left'][i], global_dict['top'][i],
                        global_dict['width'][i], global_dict['height'][i])
        self._logger.debug("Diff: {}", diff)
        click_x, click_y = (x + w / 2) / diff, (y + h / 2) / diff
        self._communicator.click(click_x, click_y)

    def __handle_screentype(self, screentype: ScreenType,
                            global_dict: Optional[dict] = None, diff: int = -1) -> ScreenType:
        if screentype == ScreenType.UNDEFINED:
            self._logger.warning("Undefined screentype, abandon ship...")
        elif screentype == ScreenType.BIRTHDATE:
            self.__handle_birthday_screen()
        elif screentype == ScreenType.RETURNING:
            self.__handle_returning_player_or_wrong_credentials()
        elif screentype == ScreenType.LOGINSELECT:
            self.__handle_login_screen(global_dict, diff)
        elif screentype == ScreenType.PTC:
            return self.__handle_ptc_login()
        elif screentype == ScreenType.FAILURE:
            self.__handle_failure_screen()
        elif screentype == ScreenType.RETRY:
            self.__handle_retry_screen(diff, global_dict)
        elif screentype == ScreenType.WRONG:
            self.__handle_returning_player_or_wrong_credentials()
            screentype = ScreenType.ERROR
        elif screentype == ScreenType.GAMEDATA:
            self._nextscreen = ScreenType.UNDEFINED
        elif screentype == ScreenType.GGL:
            screentype = self.__handle_google_login(screentype)
        elif screentype == ScreenType.PERMISSION:
            screentype = self.__handle_permissions_screen(screentype)
        elif screentype == ScreenType.CREDENTIALS:
            screentype = self.__handle_permissions_screen(screentype)
        elif screentype == ScreenType.MARKETING:
            self.__handle_marketing_screen(diff, global_dict)
        elif screentype == ScreenType.CONSENT:
            self._nextscreen = ScreenType.UNDEFINED
        elif screentype == ScreenType.SN:
            self._nextscreen = ScreenType.UNDEFINED
        elif screentype == ScreenType.UPDATE:
            self._nextscreen = ScreenType.UNDEFINED
        elif screentype == ScreenType.NOGGL:
            self._nextscreen = ScreenType.UNDEFINED
        elif screentype == ScreenType.STRIKE:
            self.__handle_strike_screen(diff, global_dict)
        elif screentype == ScreenType.SUSPENDED:
            self._nextscreen = ScreenType.UNDEFINED
            self._logger.warning('Account temporarily banned!')
            screentype = ScreenType.ERROR
        elif screentype == ScreenType.TERMINATED:
            self._nextscreen = ScreenType.UNDEFINED
            self._logger.error('Account permabanned!')
            screentype = ScreenType.ERROR
        elif screentype == ScreenType.POGO:
            screentype = self.__check_pogo_screen_ban_or_loading(screentype)
        elif screentype == ScreenType.QUEST:
            self._logger.warning("Already on quest screen")
            # TODO: consider closing quest window?
            self._nextscreen = ScreenType.UNDEFINED
        elif screentype == ScreenType.GPS:
            self._nextscreen = ScreenType.UNDEFINED
            self._logger.warning("In game error detected")
        elif screentype == ScreenType.BLACK:
            self._logger.warning("Screen is black, sleeping a couple seconds for another check...")
        elif screentype == ScreenType.CLOSE:
            self._logger.debug("Detected pogo not open")
        elif screentype == ScreenType.DISABLED:
            self._logger.warning("Screendetection disabled")
        elif screentype == ScreenType.ERROR:
            self._logger.error("Error during screentype detection")

        return screentype

    def __check_pogo_screen_ban_or_loading(self, screentype) -> ScreenType:
        backgroundcolor = self._pogoWindowManager.most_frequent_colour(self.get_screenshot_path(), self.origin)
        if backgroundcolor is not None and (
                backgroundcolor[0] == 0 and
                backgroundcolor[1] == 0 and
                backgroundcolor[2] == 0):
            # Background is black - Loading ...
            screentype = ScreenType.BLACK
        elif backgroundcolor is not None and (
                backgroundcolor[0] == 16 and
                backgroundcolor[1] == 24 and
                backgroundcolor[2] == 33):
            # Got a strike warning
            screentype = ScreenType.STRIKE
        return screentype

    def __handle_strike_screen(self, diff, global_dict) -> None:
        self._nextscreen = ScreenType.UNDEFINED
        self._logger.warning('Got a black strike warning!')
        click_text = 'GOT IT,ALLES KLAR'
        n_boxes = len(global_dict['level'])
        for i in range(n_boxes):
            if any(elem.lower() in (global_dict['text'][i].lower()) for elem in click_text.split(",")):
                self._click_center_button(diff, global_dict, i)
                time.sleep(2)

    def __handle_marketing_screen(self, diff, global_dict) -> None:
        self._nextscreen = ScreenType.POGO
        click_text = 'ERLAUBEN,ALLOW,AUTORISER'
        n_boxes = len(global_dict['level'])
        for i in range(n_boxes):
            if any(elem.lower() in (global_dict['text'][i].lower()) for elem in click_text.split(",")):
                self._click_center_button(diff, global_dict, i)
                time.sleep(2)

    def __handle_permissions_screen(self, screentype) -> ScreenType:
        self._nextscreen = ScreenType.UNDEFINED
        if not self.parse_permission(self._communicator.uiautomator()):
            screentype = ScreenType.ERROR
        time.sleep(2)
        return screentype

    def __handle_google_login(self, screentype) -> ScreenType:
        self._nextscreen = ScreenType.UNDEFINED
        if self._logintype == LoginType.ptc:
            self._logger.warning('Really dont know how i get there ... using first @ggl address ... :)')
            username = self.get_devicesettings_value('ggl_login_mail', '@gmail.com')
        else:
            ggl_login = self.get_next_account()
            username = ggl_login.username
        if self.parse_ggl(self._communicator.uiautomator(), username):
            self._logger.info("Sleeping 50 seconds - please wait!")
            time.sleep(50)
        else:
            screentype = ScreenType.ERROR
        return screentype

    def __handle_retry_screen(self, diff, global_dict) -> None:
        self._nextscreen = ScreenType.UNDEFINED
        click_text = 'DIFFERENT,AUTRE,AUTORISER,ANDERES,KONTO,ACCOUNT'
        n_boxes = len(global_dict['level'])
        for i in range(n_boxes):
            if any(elem in (global_dict['text'][i]) for elem in click_text.split(",")):
                self._click_center_button(diff, global_dict, i)
                time.sleep(2)

    def __handle_ptc_login(self) -> ScreenType:
        self._nextscreen = ScreenType.UNDEFINED
        ptc = self.get_next_account()
        if not ptc:
            self._logger.error('No PTC Username and Password is set')
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
        else:
            self._logger.error("Unhandled ratio, unlikely to be the case. Do open a github issue")
            return ScreenType.ERROR
        # username
        self._communicator.click(self._width / 2, username_y)
        time.sleep(.5)
        self._communicator.enter_text(ptc.username)
        self._communicator.click(100, 100)
        time.sleep(2)
        # password
        self._communicator.click(self._width / 2, password_y)
        time.sleep(.5)
        self._communicator.enter_text(ptc.password)
        self._communicator.click(100, 100)
        time.sleep(2)
        # button
        self._communicator.click(self._width / 2, button_y)
        self._logger.info("Sleeping 50 seconds - please wait!")
        time.sleep(50)
        return ScreenType.PTC

    def __handle_failure_screen(self) -> None:
        self.__handle_returning_player_or_wrong_credentials()

    def __handle_returning_player_or_wrong_credentials(self) -> None:
        self._nextscreen = ScreenType.UNDEFINED
        self._pogoWindowManager.look_for_button(self.origin, self.get_screenshot_path(), 2.20, 3.01, self._communicator,
                                                upper=True)
        time.sleep(2)

    def __handle_birthday_screen(self) -> None:
        self._nextscreen = ScreenType.RETURNING
        click_x = (self._width / 2) + (self._width / 4)
        click_y = (self._height / 1.69) + self._screenshot_y_offset
        self._communicator.click(click_x, click_y)
        self._communicator.touch_and_hold(click_x, click_y, click_x, click_y - (self._height / 2), 200)
        time.sleep(1)
        self._communicator.touch_and_hold(click_x, click_y, click_x, click_y - (self._height / 2), 200)
        time.sleep(1)
        self._communicator.click(click_x, click_y)
        time.sleep(1)
        click_x = self._width / 2
        click_y = click_y + (self._height / 8.53)
        self._communicator.click(click_x, click_y)
        time.sleep(1)

    def detect_screentype(self) -> ScreenType:
        topmostapp = self._communicator.topmost_app()
        if not topmostapp:
            self._logger.warning("Failed getting the topmost app!")
            return ScreenType.ERROR

        screentype, global_dict, diff = self.__evaluate_topmost_app(topmost_app=topmostapp)
        self._logger.info("Processing Screen: {}", str(ScreenType(screentype)))
        return self.__handle_screentype(screentype=screentype, global_dict=global_dict, diff=diff)

    def checkQuest(self, screenpath: str) -> ScreenType:
        if screenpath is None or len(screenpath) == 0:
            self._logger.error("Invalid screen path: {}", screenpath)
            return ScreenType.ERROR
        globaldict = self._pogoWindowManager.get_screen_text(screenpath, self.origin)

        click_text = 'FIELD,SPECIAL,FELD,SPEZIAL,SPECIALES,TERRAIN'
        if not globaldict:
            # dict is empty
            return ScreenType.ERROR
        n_boxes = len(globaldict['level'])
        for i in range(n_boxes):
            if any(elem in (globaldict['text'][i]) for elem in click_text.split(",")):
                self._logger.info('Found research menu')
                self._communicator.click(100, 100)
                return ScreenType.QUEST

        self._logger.info('Listening to Dr. blabla - please wait')

        self._communicator.back_button()
        time.sleep(3)
        return ScreenType.UNDEFINED

    def parse_permission(self, xml) -> bool:
        if xml is None:
            self._logger.warning('Something wrong with processing - getting None Type from Websocket...')
            return False
        click_text = ('ZULASSEN', 'ALLOW', 'AUTORISER', 'OK')
        try:
            parser = ET.XMLParser(encoding="utf-8")
            xmlroot = ET.fromstring(xml, parser=parser)
            bounds: str = ""
            for item in xmlroot.iter('node'):
                if str(item.attrib['text']).upper() in click_text:
                    self._logger.debug("Found text {}", item.attrib['text'])
                    bounds = item.attrib['bounds']
                    self._logger.debug("Bounds {}", item.attrib['bounds'])

                    match = re.search(r'^\[(\d+),(\d+)\]\[(\d+),(\d+)\]$', bounds)

                    click_x = int(match.group(1)) + ((int(match.group(3)) - int(match.group(1))) / 2)
                    click_y = int(match.group(2)) + ((int(match.group(4)) - int(match.group(2))) / 2)
                    self._communicator.click(click_x, click_y)
                    time.sleep(2)
                    return True
        except Exception as e:
            self._logger.error('Something wrong while parsing xml: {}', e)
            return False

        time.sleep(2)
        self._logger.warning('Dont find any button...')
        return False

    def parse_ggl(self, xml, mail: str) -> bool:
        if xml is None:
            self._logger.warning('Something wrong with processing - getting None Type from Websocket...')
            return False
        try:
            parser = ET.XMLParser(encoding="utf-8")
            xmlroot = ET.fromstring(xml, parser=parser)
            for item in xmlroot.iter('node'):
                if mail.lower() in str(item.attrib['text']).lower():
                    self._logger.info("Found mail {}", self.censor_account(str(item.attrib['text'])))
                    bounds = item.attrib['bounds']
                    self._logger.debug("Bounds {}", item.attrib['bounds'])
                    match = re.search(r'^\[(\d+),(\d+)\]\[(\d+),(\d+)\]$', bounds)
                    click_x = int(match.group(1)) + ((int(match.group(3)) - int(match.group(1))) / 2)
                    click_y = int(match.group(2)) + ((int(match.group(4)) - int(match.group(2))) / 2)
                    self._communicator.click(click_x, click_y)
                    time.sleep(2)
                    return True
        except Exception as e:
            self._logger.error('Something wrong while parsing xml: {}', e)
            return False

        time.sleep(2)
        self._logger.warning('Dont find any mailaddress...')
        return False

    def set_devicesettings_value(self, key: str, value) -> None:
        self._mapping_manager.set_devicesetting_value_of(self.origin, key, value)

    def get_devicesettings_value(self, key: str, default_value: object = None):
        self._logger.debug2("Fetching devicemappings")
        try:
            devicemappings: Optional[dict] = self._mapping_manager.get_devicemappings_of(self.origin)
        except (EOFError, FileNotFoundError) as e:
            self._logger.warning("Failed fetching devicemappings in worker with description: {}. Stopping worker", e)
            return None
        if devicemappings is None:
            return default_value
        return devicemappings.get("settings", {}).get(key, default_value)

    def censor_account(self, emailaddress, isPTC=False):
        # PTC account
        if isPTC:
            return (emailaddress[0:2] + "***" + emailaddress[-2:])
        # GGL - make sure we have @ there.
        # If not it could be wrong match, so returning original
        if '@' in emailaddress:
            user, domain = emailaddress.split("@", 1)
            # long local-part, censor middle part only
            if len(user) > 6:
                return (user[0:2] + "***" + user[-2:] + "@" + domain)
            # domain only, just return
            elif len(user) == 0:
                return (emailaddress)
            # local-part is short, asterix for each char
            else:
                return ("*" * len(user) + "@" + domain)
        return emailaddress

    def get_screenshot_path(self, fileaddon: bool = False) -> str:
        screenshot_ending: str = ".jpg"
        addon: str = ""
        if self.get_devicesettings_value("screenshot_type", "jpeg") == "png":
            screenshot_ending = ".png"

        if fileaddon:
            addon: str = "_" + str(time.time())

        screenshot_filename = "screenshot_{}{}{}".format(str(self.origin), str(addon), screenshot_ending)

        if fileaddon:
            self._logger.info("Creating debugscreen: {}", screenshot_filename)

        return os.path.join(
            self._applicationArgs.temp_path, screenshot_filename)

    def _takeScreenshot(self, delayAfter=0.0, delayBefore=0.0, errorscreen: bool = False):
        self._logger.debug("Taking screenshot...")
        time.sleep(delayBefore)

        # TODO: area settings for jpg/png and quality?
        screenshot_type: ScreenshotType = ScreenshotType.JPEG
        if self.get_devicesettings_value("screenshot_type", "jpeg") == "png":
            screenshot_type = ScreenshotType.PNG

        screenshot_quality: int = 80

        take_screenshot = self._communicator.get_screenshot(self.get_screenshot_path(fileaddon=errorscreen),
                                                            screenshot_quality, screenshot_type)

        if not take_screenshot:
            self._logger.error("takeScreenshot: Failed retrieving screenshot")
            self._logger.debug("Failed retrieving screenshot")
            return False
        else:
            self._logger.debug("Success retrieving screenshot")
            self._lastScreenshotTaken = time.time()
            time.sleep(delayAfter)
            return True
