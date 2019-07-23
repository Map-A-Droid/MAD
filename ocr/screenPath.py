import cv2
import pytesseract
import math
import time
import re

import xml.etree.ElementTree as ET
from utils.logging import logger
from utils.MappingManager import MappingManager
from typing import Optional, List
from pytesseract import Output
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
    POGO = 99
    GGL = 10
    PERMISSION = 11
    MARKETING = 12
    QUEST = 20
    ERROR = 100

class LoginType(Enum):
    UNKNOWN = -1
    google = 1
    ptc = 2


class WordToScreenMatching(object):
    def __init__(self, communicator, pogoWindowManager, id, resocalc, mapping_mananger: MappingManager):
        self._ScreenType: dict = {}
        self._id = id
        self._mapping_manager = mapping_mananger
        detect_ReturningScreen: list = ('ZURUCKKEHRENDER', 'ZURÜCKKEHRENDER', 'GAME', 'FREAK', 'SPIELER')
        detect_LoginScreen: list = ('KIDS', 'Google', 'Facebook')
        detect_PTC: list = ('Benutzername', 'Passwort', 'Username', 'Password','DRESSEURS')
        detect_FailureRetryScreen: list = ('TRY', 'DIFFERENT', 'ACCOUNT', 'Anmeldung', 'Konto', 'anderes',
                                           'connexion.', 'connexion')
        detect_FailureLoginScreen: list = ('Authentifizierung', 'fehlgeschlagen', 'Unable', 'authenticate',
                                           'Authentification', 'Essaye')
        detect_WrongPassword: list = ('incorrect.', 'attempts', 'falsch.', 'gesperrt')
        detect_Birthday: list = ('Geburtdatum', 'birth.', 'naissance.', 'date')
        detect_Marketing: list = ('Events,', 'Benachrichtigungen', 'Einstellungen', 'events,', 'offers,',
                                  'notifications', 'évenements,', 'evenements,', 'offres')
        self._ScreenType[2] = detect_ReturningScreen
        self._ScreenType[3] = detect_LoginScreen
        self._ScreenType[4] = detect_PTC
        self._ScreenType[5] = detect_FailureLoginScreen
        self._ScreenType[6] = detect_FailureRetryScreen
        self._ScreenType[1] = detect_Birthday
        self._ScreenType[12] = detect_Marketing
        self._ScreenType[7] = detect_WrongPassword
        self._globaldict: dict = []

        self._logintype: LoginType = -1
        self._PTC_accounts: List[Login_PTC] = []
        self._GGL_accounts: List[Login_GGL] = []
        self._accountcount: int = 0
        self._accountindex: int = self.get_devicesettings_value('accountindex', 0)

        self._pogoWindowManager = pogoWindowManager
        self._communicator = communicator
        self._resocalc = resocalc
        logger.info("Starting Screendetector")
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
            logger.info('Using PTC Account: {}'.format(self._PTC_accounts[self._accountindex-1].username))
            return self._PTC_accounts[self._accountindex-1]
        else:
            logger.info('Using GGL Account: {}'.format(self._GGL_accounts[self._accountindex - 1].username))
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

    def matchScreen(self, screenpath):
        topmostapp = self._communicator.topmostApp()
        if not topmostapp:
            return ScreenType.ERROR
        frame = cv2.imread(screenpath)
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        returntype: ScreenType = -1
        self._globaldict = pytesseract.image_to_data(frame, output_type=Output.DICT)
        if "AccountPickerActivity" in topmostapp or 'SignInActivity' in topmostapp:
            returntype= 10
        elif "GrantPermissionsActivity" in topmostapp:
            returntype = 11
        else:
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
            n_boxes = len(self._globaldict['level'])
            ggl_login = self.get_next_account()
            for i in range(n_boxes):
                if ggl_login.username in (self._globaldict['text'][i]):
                    (x, y, w, h) = (self._globaldict['left'][i], self._globaldict['top'][i],
                                    self._globaldict['width'][i], self._globaldict['height'][i])
                    click_x, click_y = x + w / 2, y + h / 2
                    logger.debug('Click ' + str(click_x) + ' / ' + str(click_y))
                    self._communicator.click(click_x, click_y)
                    time.sleep(25)

                    return ScreenType.GGL

            logger.warning('Dont find saved login mail address')
            return ScreenType.ERROR

        elif ScreenType(returntype) == ScreenType.PERMISSION:
            (click_x, click_y) = self.parseXML(self._communicator.uiautomator())
            self._communicator.click(click_x, click_y)
            time.sleep(2)
            return ScreenType.PERMISSION

        elif ScreenType(returntype) == ScreenType.MARKETING:
            click_text = 'ERLAUBEN,ALLOW,AUTORISER'
            n_boxes = len(self._globaldict['level'])
            for i in range(n_boxes):
                if any(elem.lower() in (self._globaldict['text'][i].lower()) for elem in click_text.split(",")):
                    (x, y, w, h) = (self._globaldict['left'][i], self._globaldict['top'][i],
                                    self._globaldict['width'][i], self._globaldict['height'][i])
                    click_x, click_y = x + w / 2, y + h / 2
                    logger.debug('Click ' + str(click_x) + ' / ' + str(click_y))
                    self._communicator.click(click_x, click_y)
                    time.sleep(2)

            return ScreenType.MARKETING

        elif ScreenType(returntype) == ScreenType.BIRTHDATE:
            height, width = frame.shape
            old_y = None
            frame = cv2.GaussianBlur(frame, (3, 3), 0)
            frame = cv2.Canny(frame, 50, 200, apertureSize=3)
            kernel = np.ones((2, 2), np.uint8)
            edges = cv2.morphologyEx(frame, cv2.MORPH_GRADIENT, kernel)
            minLineLength = (width / 3.927272727272727) - (width * 0.02)
            lines = cv2.HoughLinesP(edges, rho=1, theta=math.pi / 180, threshold=70, minLineLength=minLineLength,
                                    maxLineGap=2)

            lines = self.check_lines(lines, height)
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
                        self._communicator.touchandhold(click_x, click_y, click_x, click_y - (height/2), 200)
                        time.sleep(1)
                        self._communicator.click(click_x, click_y)
                        time.sleep(1)
                        click_x = width / 2
                        click_y = click_y + (height / 8.53)
                        self._communicator.click(click_x, click_y)
                        time.sleep(1)
                        return ScreenType.BIRTHDATE

        elif ScreenType(returntype) == ScreenType.RETURNING:
            self._pogoWindowManager.look_for_button(screenpath, 2.20, 3.01, self._communicator, upper=True)
            time.sleep(2)
            return ScreenType.RETURNING

        elif ScreenType(returntype) == ScreenType.WRONG:
            self._pogoWindowManager.look_for_button(screenpath, 2.20, 3.01, self._communicator, upper=True)
            time.sleep(2)
            return ScreenType.ERROR

        elif ScreenType(returntype) == ScreenType.LOGINSELECT:
            temp_dict: dict = {}
            n_boxes = len(self._globaldict['level'])
            for i in range(n_boxes):
                if 'Facebook' in (self._globaldict['text'][i]): temp_dict['Facebook'] = self._globaldict['top'][i]
                if 'CLUB' in (self._globaldict['text'][i]): temp_dict['CLUB'] = self._globaldict['top'][i]
                # french ...
                if 'DRESSEURS' in (self._globaldict['text'][i]): temp_dict['TRAINER'] = self._globaldict['top'][i]

                if self.get_devicesettings_value('logintype', 'google') == 'ptc':
                    if 'CLUB' in (self._globaldict['text'][i]):
                        (x, y, w, h) = (self._globaldict['left'][i], self._globaldict['top'][i],
                                        self._globaldict['width'][i], self._globaldict['height'][i])
                        click_x, click_y = x + w / 2, y + h / 2
                        logger.debug('Click ' + str(click_x) + ' / ' + str(click_y))
                        self._communicator.click(click_x, click_y)
                        time.sleep(1)
                        return ScreenType.LOGINSELECT

                else:

                    if 'Google' in (self._globaldict['text'][i]):
                        (x, y, w, h) = (self._globaldict['left'][i], self._globaldict['top'][i],
                                        self._globaldict['width'][i], self._globaldict['height'][i])
                        click_x, click_y = x + w / 2, y + h / 2
                        logger.debug('Click ' + str(click_x) + ' / ' + str(click_y))
                        self._communicator.click(click_x, click_y)
                        time.sleep(1)
                        return ScreenType.LOGINSELECT

                    # alternative select
                    if 'Facebook' in temp_dict and 'TRAINER' in temp_dict:
                        height, width = frame.shape
                        click_x = width / 2
                        click_y = temp_dict['Facebook'] + ((temp_dict['TRAINER'] - temp_dict['Facebook']) / 2)
                        logger.debug('Click ' + str(click_x) + ' / ' + str(click_y))
                        self._communicator.click(click_x, click_y)
                        time.sleep(2)
                        return ScreenType.LOGINSELECT

                    # alternative select
                    if 'Facebook' in temp_dict:
                        height, width = frame.shape
                        click_x = width / 2
                        click_y = temp_dict['Facebook'] + (height / 10.11)
                        logger.debug('Click ' + str(click_x) + ' / ' + str(click_y))
                        self._communicator.click(click_x, click_y)
                        time.sleep(2)
                        return ScreenType.LOGINSELECT

                    # alternative select
                    if 'CLUB' in temp_dict:
                        height, width = frame.shape
                        click_x = width / 2
                        click_y = temp_dict['TRAINER'] - (height / 10.11)
                        logger.debug('Click ' + str(click_x) + ' / ' + str(click_y))
                        self._communicator.click(click_x, click_y)
                        time.sleep(2)
                        return ScreenType.LOGINSELECT

        elif ScreenType(returntype) == ScreenType.PTC:
            click_user_text = 'Username,Benutzername,Nom,d’utilisateur'
            click_pass_text = 'Password,Passwort,Mot,passe'
            ptc = self.get_next_account()
            if not ptc:
                logger.error('No PTC Username and Password is set')
                return ScreenType.ERROR

            for i in range(n_boxes):
                if any(elem in (self._globaldict['text'][i]) for elem in click_user_text.split(",")):
                    (x, y, w, h) = (self._globaldict['left'][i], self._globaldict['top'][i],
                                    self._globaldict['width'][i], self._globaldict['height'][i])
                    click_x, click_y = x + w / 2, y + h / 2
                    logger.debug('Click ' + str(click_x) + ' / ' + str(click_y))
                    self._communicator.click(click_x, click_y)
                    time.sleep(.5)
                    self._communicator.sendText(ptc.username)
                    break

            self._communicator.click(100, 100)

            for i in range(n_boxes):
                if any(elem.lower() in (self._globaldict['text'][i].lower()) for elem in click_pass_text.split(",")):
                    (x, y, w, h) = (self._globaldict['left'][i], self._globaldict['top'][i],
                                    self._globaldict['width'][i], self._globaldict['height'][i])
                    click_x, click_y = x + w / 2, y + h / 2
                    logger.debug('Click ' + str(click_x) + ' / ' + str(click_y))
                    self._communicator.click(click_x, click_y)
                    time.sleep(.5)
                    self._communicator.sendText(ptc.password)
                    time.sleep(2)
                    break

            self._communicator.click(100, 100)
            time.sleep(2)

            self._pogoWindowManager.look_for_button(screenpath, 2.20, 3.01, self._communicator)
            time.sleep(25)
            return ScreenType.PTC

        elif ScreenType(returntype) == ScreenType.FAILURE:
            self._pogoWindowManager.look_for_button(screenpath, 2.20, 3.01, self._communicator)
            time.sleep(2)
            return ScreenType.ERROR

        elif ScreenType(returntype) == ScreenType.RETRY:
            click_text = 'DIFFERENT,AUTRE,AUTORISER,ANDERES,KONTO,ACCOUNT'
            n_boxes = len(self._globaldict['level'])
            for i in range(n_boxes):
                if any(elem in (self._globaldict['text'][i]) for elem in click_text.split(",")):
                    (x, y, w, h) = (self._globaldict['left'][i], self._globaldict['top'][i],
                                    self._globaldict['width'][i], self._globaldict['height'][i])
                    click_x, click_y = x + w / 2, y + h / 2
                    logger.debug('Click ' + str(click_x) + ' / ' + str(click_y))
                    self._communicator.click(click_x, click_y)
                    time.sleep(2)
            return ScreenType.RETRY

        else:
            return ScreenType.POGO

    def checkQuest(self, screenpath):
        frame = cv2.imread(screenpath)
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        self._globaldict = pytesseract.image_to_data(frame, output_type=Output.DICT)
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

    def parseXML(self, xml):
        click_text = ('ZULASSEN', 'ALLOW', 'AUTORISER')
        parser = ET.XMLParser(encoding="utf-8")
        xmlroot = ET.fromstring(xml, parser=parser)
        bounds: str = ""
        for item in xmlroot.iter('node'):
            if str(item.attrib['text']).upper() in click_text:
                logger.debug("Found text {}", str(item.attrib['text']))
                bounds = item.attrib['bounds']
                logger.debug("Bounds {}", str(item.attrib['bounds']))
                continue

        match = re.search(r'^\[(\d+),(\d+)\]\[(\d+),(\d+)\]$', bounds)

        click_x = int(match.group(1)) + ((int(match.group(3)) - int(match.group(1)))/2)
        click_y = int(match.group(2)) + ((int(match.group(4)) - int(match.group(2)))/2)
        logger.debug('Click ' + str(click_x) + ' / ' + str(click_y))

        return click_x, click_y

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


if __name__ == '__main__':
    screen = WordToScreenMatching(None, None, "test")
    screen.matchScreen("screenshot_tv_grant.jpg")
