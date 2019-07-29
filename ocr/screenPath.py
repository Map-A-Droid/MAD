import cv2
import math
import time
import re
import sys
sys.path.append("..")
import xml.etree.ElementTree as ET
from utils.logging import logger
from utils.MappingManager import MappingManager
from typing import Optional, List
from multiprocessing.pool import ThreadPool
from utils.collections import Login_PTC, Login_GGL
from enum import Enum
import numpy as np

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
    QUEST = 20
    ERROR = 100
    CLOSE = 500

class LoginType(Enum):
    UNKNOWN = -1
    google = 1
    ptc = 2


class WordToScreenMatching(object):
    def __init__(self, communicator, pogoWindowManager, id, resocalc, mapping_mananger: MappingManager, worker):
        self._ScreenType: dict = {}
        self._id = id
        self._parent = worker
        self._mapping_manager = mapping_mananger
        detect_ReturningScreen: list = ('ZURUCKKEHRENDER', 'ZURÜCKKEHRENDER', 'GAME', 'FREAK', 'SPIELER')
        detect_LoginScreen: list = ('KIDS', 'Google', 'Facebook')
        detect_PTC: list = ('Benutzername', 'Passwort', 'Username', 'Password', 'DRESSEURS')
        detect_FailureRetryScreen: list = ('TRY', 'DIFFERENT', 'ACCOUNT', 'Anmeldung', 'Konto', 'anderes',
                                           'connexion.', 'connexion')
        detect_FailureLoginScreen: list = ('Authentifizierung', 'fehlgeschlagen', 'Unable', 'authenticate',
                                           'Authentification', 'Essaye')
        detect_WrongPassword: list = ('incorrect.', 'attempts', 'falsch.', 'gesperrt')
        detect_Birthday: list = ('Geburtdatum', 'birth.', 'naissance.', 'date')
        detect_Marketing: list = ('Events,', 'Benachrichtigungen', 'Einstellungen', 'events,', 'offers,',
                                  'notifications', 'évenements,', 'evenements,', 'offres')
        detect_Gamedata: list = ('Spieldaten', 'abgerufen', 'lecture', 'depuis', 'server', 'data')
        self._ScreenType[2] = detect_ReturningScreen
        self._ScreenType[3] = detect_LoginScreen
        self._ScreenType[4] = detect_PTC
        self._ScreenType[5] = detect_FailureLoginScreen
        self._ScreenType[6] = detect_FailureRetryScreen
        self._ScreenType[8] = detect_Gamedata
        self._ScreenType[1] = detect_Birthday
        self._ScreenType[12] = detect_Marketing
        self._ScreenType[7] = detect_WrongPassword
        self._globaldict: dict = []
        self._ratio: float = 0.0

        self._logintype: LoginType = -1
        self._PTC_accounts: List[Login_PTC] = []
        self._GGL_accounts: List[Login_GGL] = []
        self._accountcount: int = 0
        self._accountindex: int = self.get_devicesettings_value('accountindex', 0)
        self._nextscreen: ScreenType = ScreenType.UNDEFINED

        self._pogoWindowManager = pogoWindowManager
        self._communicator = communicator
        self._resocalc = resocalc
        logger.info("Starting Screendetector")
        self._width: int = 0
        self._height: int = 0
        self.__thread_pool = ThreadPool(processes=2)
        self.get_login_accounts()

    def get_login_accounts(self):
        self._logintype = LoginType[self.get_devicesettings_value('logintype', 'google')]
        logger.info("Set logintype: {}".format(self._logintype))
        if self._logintype == LoginType.ptc:
            temp_accounts = self.get_devicesettings_value('ptc_login', False)
            if not temp_accounts:
                logger.warning('No PTC Accounts are set - hope we are login and never logout!')
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
            logger.info('Using PTC Account: {}'.format(self.censor_account(self._PTC_accounts[self._accountindex-1].username, isPTC=True)))
            return self._PTC_accounts[self._accountindex-1]
        else:
            logger.info('Using GGL Account: {}'.format(self.censor_account(self._GGL_accounts[self._accountindex-1].username)))
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
        return self.__thread_pool.apply_async(self.__internal_matchScreen, ()).get()

    def __internal_matchScreen(self):
        pogoTopmost = self._communicator.isPogoTopmost()
        screenpath = self._parent.get_screenshot_path()
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
        else:
            if not self._parent._takeScreenshot(delayBefore=self.get_devicesettings_value("post_screenshot_delay", 1),
                                                delayAfter=2):
                logger.error("_check_windows: Failed getting screenshot")
                return ScreenType.ERROR
            try:
                frame_org = cv2.imread(screenpath)
            except Exception:
                logger.error("Screenshot corrupted :(")
                return ScreenType.ERROR

            if frame_org is None:
                logger.error("Screenshot corrupted :(")
                return ScreenType.ERROR

            self._height, self._width, _ = frame_org.shape
            frame_color = cv2.resize(frame_org, None, fx=2, fy=2)
            frame = cv2.cvtColor(frame_color, cv2.COLOR_BGR2GRAY)
            self._ratio = self._height / self._width
            self._globaldict = self._pogoWindowManager.get_screen_text(frame, self._id)
            if 'text' not in self._globaldict:
                logger.error('Error while text detection')
                return ScreenType.ERROR
            n_boxes = len(self._globaldict['level'])
            for i in range(n_boxes):
                if returntype != -1: break
                if len(self._globaldict['text'][i]) > 3:
                    for z in self._ScreenType:
                        if self._globaldict['text'][i] in self._ScreenType[z]:
                            returntype = z

        if ScreenType(returntype) != ScreenType.UNDEFINED:
            logger.info("Processing Screen: {}", str(ScreenType(returntype)))

        if ScreenType(returntype) == ScreenType.GGL:
            self._nextscreen = ScreenType.UNDEFINED
            ggl_login = self.get_next_account()
            if self.parse_ggl(self._communicator.uiautomator(), ggl_login.username):
                time.sleep(25)
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
            time.sleep(2)
            return ScreenType.CONSENT

        elif ScreenType(returntype) == ScreenType.GAMEDATA:
            self._nextscreen = ScreenType.UNDEFINED
            return ScreenType.GAMEDATA

        elif ScreenType(returntype) == ScreenType.MARKETING:
            self._nextscreen = ScreenType.POGO
            click_text = 'ERLAUBEN,ALLOW,AUTORISER'
            n_boxes = len(self._globaldict['level'])
            for i in range(n_boxes):
                if any(elem.lower() in (self._globaldict['text'][i].lower()) for elem in click_text.split(",")):
                    (x, y, w, h) = (self._globaldict['left'][i], self._globaldict['top'][i],
                                    self._globaldict['width'][i], self._globaldict['height'][i])
                    click_x, click_y = (x + w / 2) / 2, (y + h / 2) / 2
                    logger.debug('Click ' + str(click_x) + ' / ' + str(click_y))
                    self._communicator.click(click_x, click_y)
                    time.sleep(2)

            return ScreenType.MARKETING

        elif ScreenType(returntype) == ScreenType.BIRTHDATE:
            self._nextscreen = ScreenType.UNDEFINED
            old_y = None
            frame = cv2.cvtColor(frame_org, cv2.COLOR_BGR2GRAY)
            frame = cv2.GaussianBlur(frame, (3, 3), 0)
            frame = cv2.Canny(frame, 50, 200, apertureSize=3)
            kernel = np.ones((2, 2), np.uint8)
            edges = cv2.morphologyEx(frame, cv2.MORPH_GRADIENT, kernel)
            minLineLength = (self._width / 3.927272727272727) - (self._width * 0.02)
            lines = cv2.HoughLinesP(edges, rho=1, theta=math.pi / 180, threshold=70, minLineLength=minLineLength,
                                    maxLineGap=2)

            lines = self.check_lines(lines, self._height)
            for line in lines:
                line = [line]
                for x1, y1, x2, y2 in line:
                    if old_y is None:
                        old_y = y1
                    else:
                        click_y = old_y + ((y1 - old_y)/2)
                        click_x = x1 + ((x2 - x1)/2)
                        logger.debug('Click ' + str(click_x) + ' / ' + str(click_y))
                        self._communicator.click(click_x, click_y)
                        self._communicator.touchandhold(click_x, click_y, click_x, click_y - (self._height/2), 200)
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
            n_boxes = len(self._globaldict['level'])
            for i in range(n_boxes):
                if 'Facebook' in (self._globaldict['text'][i]): temp_dict['Facebook'] = self._globaldict['top'][i] / 2
                if 'CLUB' in (self._globaldict['text'][i]): temp_dict['CLUB'] = self._globaldict['top'][i] / 2
                # french ...
                if 'DRESSEURS' in (self._globaldict['text'][i]): temp_dict['CLUB'] = self._globaldict['top'][i] / 2

                if self.get_devicesettings_value('logintype', 'google') == 'ptc':
                    self._nextscreen = ScreenType.PTC
                    if 'CLUB' in (self._globaldict['text'][i]):
                        (x, y, w, h) = (self._globaldict['left'][i], self._globaldict['top'][i],
                                        self._globaldict['width'][i], self._globaldict['height'][i])
                        click_x, click_y = (x + w / 2) / 2, (y + h / 2) / 2
                        logger.debug('Click ' + str(click_x) + ' / ' + str(click_y))
                        self._communicator.click(click_x, click_y)
                        time.sleep(5)
                        return ScreenType.LOGINSELECT

                else:
                    self._nextscreen = ScreenType.UNDEFINED
                    if 'Google' in (self._globaldict['text'][i]):
                        (x, y, w, h) = (self._globaldict['left'][i], self._globaldict['top'][i],
                                        self._globaldict['width'][i], self._globaldict['height'][i])
                        click_x, click_y = (x + w / 2) / 2, (y + h / 2) / 2
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

            username_y = self._height / 2.224797219003476
            password_y = self._height / 1.875
            button_y = self._height / 1.58285243198681

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
            time.sleep(25)
            return ScreenType.PTC

        elif ScreenType(returntype) == ScreenType.FAILURE:
            self._nextscreen = ScreenType.UNDEFINED
            self._pogoWindowManager.look_for_button(screenpath, 2.20, 3.01, self._communicator)
            time.sleep(2)
            return ScreenType.ERROR

        elif ScreenType(returntype) == ScreenType.RETRY:
            self._nextscreen = ScreenType.UNDEFINED
            click_text = 'DIFFERENT,AUTRE,AUTORISER,ANDERES,KONTO,ACCOUNT'
            n_boxes = len(self._globaldict['level'])
            for i in range(n_boxes):
                if any(elem in (self._globaldict['text'][i]) for elem in click_text.split(",")):
                    (x, y, w, h) = (self._globaldict['left'][i], self._globaldict['top'][i],
                                    self._globaldict['width'][i], self._globaldict['height'][i])
                    click_x, click_y = (x + w / 2) / 2, (y + h / 2) / 2
                    logger.debug('Click ' + str(click_x) + ' / ' + str(click_y))
                    self._communicator.click(click_x, click_y)
                    time.sleep(2)
            return ScreenType.RETRY

        else:
            return ScreenType.POGO

    def checkQuest(self, screenpath):
        try:
            frame = cv2.imread(screenpath)
        except Exception:
            logger.error("Screenshot corrupted :(")
            return ScreenType.UNDEFINED

        if frame is None:
            logger.error("Screenshot corrupted :(")
            return ScreenType.ERROR
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        self._globaldict = self._pogoWindowManager.get_screen_text(frame, self._id)
            #pytesseract.image_to_data(frame, output_type=Output.DICT)
        click_text = 'FIELD,SPECIAL,FELD,SPEZIAL,SPECIALES,TERRAIN'
        n_boxes = len(self._globaldict['level'])
        for i in range(n_boxes):
            if any(elem in (self._globaldict['text'][i]) for elem in click_text.split(",")):
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
        time.sleep(2)
        logger.warning('Dont find any button...')
        return False

    def parse_ggl(self, xml, mail: str):
        if xml is None:
            logger.warning('Something wrong with processing - getting None Type from Websocket...')
            return False
        parser = ET.XMLParser(encoding="utf-8")
        xmlroot = ET.fromstring(xml, parser=parser)
        for item in xmlroot.iter('node'):
            if mail in str(item.attrib['text']):
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


if __name__ == '__main__':
    screen = WordToScreenMatching(None, None, "test")
    screen.matchScreen("screenshot_tv_grant.jpg")
    #frame = cv2.imread('screenshot.jpg')
    #h, w, _ = frame.shape
    #frame = cv2.resize(frame, None, fx=2, fy=2)
    #frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    #self._height, self._width, _ = frame.shape
    #print(pytesseract.image_to_data(frame, output_type=Output.DICT))

