import cv2
import pytesseract
import math
import time
import re

import xml.etree.ElementTree as ET
from utils.logging import logger
from pytesseract import Output
from enum import Enum
import numpy as np

class ScreenType(Enum):
    UNDEFINED = -1
    RETURNING = 2
    LOGINSELECT = 3
    PTC = 4
    BIRTHDATE = 1
    FAILURE = 5
    RETRY = 6
    POGO = 99
    GGL = 10
    PERMISSION = 11
    MARKETING = 12


class WordToScreenMatching(object):
    def __init__(self, communicator, pogoWindowManager, id):
        self._ScreenType: dict = {}
        self._id = id
        detect_ReturningScreen: list = ('ZURUCKKEHRENDER', 'ZURÜCKKEHRENDER', 'GAME', 'FREAK', 'SPIELER')
        detect_LoginScreen: list = ('TRAINER', 'CLUB', 'KIDS', 'Google', 'Facebook')
        detect_PTC: list = ('TRAINER-CLUB', 'Benutzername', 'Passwort')
        detect_FailureRetryScreen: list = ('TRY', 'DIFFERENT', 'ACCOUNT', 'Anmeldung', 'Konto', 'anderes',
                                           'connexion.', 'connexion')
        detect_FailureLoginScreen: list = ('Authentifizierung', 'fehlgeschlagen', 'Unable', 'authenticate',
                                           'Authentification', 'Essaye')
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
        self._globaldict: dict = []
        self._pogoWindowManager = pogoWindowManager
        self._communicator = communicator
        logger.info("Starting Screendetector")

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
        frame = cv2.imread(screenpath)
        frame_original = frame.copy()
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        self.returntype: ScreenType = -1
        self._globaldict = pytesseract.image_to_data(frame, output_type=Output.DICT)
        if "AccountPickerActivity" in topmostapp or 'SignInActivity' in topmostapp:
            self.returntype= 10
        elif "GrantPermissionsActivity" in topmostapp:
            self.returntype = 11
        else:
            n_boxes = len(self._globaldict['level'])
            for i in range(n_boxes):
                if self.returntype != -1: break
                if len(self._globaldict['text'][i]) > 3:
                    for z in self._ScreenType:
                        if self._globaldict['text'][i] in self._ScreenType[z]:
                            self.returntype = z

        if ScreenType(self.returntype) != ScreenType.UNDEFINED:
            logger.info("Processing Screen: {}", str(ScreenType(self.returntype)))

        if ScreenType(self.returntype) == ScreenType.GGL:
            n_boxes = len(self._globaldict['level'])
            for i in range(n_boxes):
                if '@gmail.com' in (self._globaldict['text'][i]):
                    (x, y, w, h) = (self._globaldict['left'][i], self._globaldict['top'][i],
                                    self._globaldict['width'][i], self._globaldict['height'][i])
                    click_x, click_y = x + w / 2, y + h / 2
                    logger.debug('Click ' + str(click_x) + ' / ' + str(click_y))
                    self._communicator.click(click_x, click_y)
                    time.sleep(25)

                    return ScreenType.GGL

        elif ScreenType(self.returntype) == ScreenType.PERMISSION:
            (click_x, click_y) = self.parseXML(self._communicator.uiautomator())
            self._communicator.click(click_x, click_y)
            time.sleep(2)
            return ScreenType.PERMISSION

        elif ScreenType(self.returntype) == ScreenType.MARKETING:
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

        elif ScreenType(self.returntype) == ScreenType.BIRTHDATE:
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
                        self._communicator.touchandhold(click_x, click_y, click_x, click_y - (height/2))
                        # self._communicator.touchandhold(click_x, click_y, click_x, click_y - (height/2))
                        time.sleep(1)
                        self._communicator.click(click_x, click_y)
                        time.sleep(1)
                        click_x = width / 2
                        click_y = click_y + (height / 8.53)
                        self._communicator.click(click_x, click_y)
                        time.sleep(1)
                        return ScreenType.BIRTHDATE

        elif ScreenType(self.returntype) == ScreenType.RETURNING:
            self._pogoWindowManager.look_for_button(screenpath, 2.20, 3.01, self._communicator)
            time.sleep(2)
            return ScreenType.RETURNING

        elif ScreenType(self.returntype) == ScreenType.LOGINSELECT:
            temp_dict: dict = {}
            n_boxes = len(self._globaldict['level'])
            for i in range(n_boxes):
                if 'Facebook' in (self._globaldict['text'][i]): temp_dict['Facebook'] = self._globaldict['top'][i]
                if 'TRAINER' in (self._globaldict['text'][i]): temp_dict['TRAINER'] = self._globaldict['top'][i]
                # french ...
                if 'DRESSEURS' in (self._globaldict['text'][i]): temp_dict['TRAINER'] = self._globaldict['top'][i]

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
                if 'TRAINER' in temp_dict:
                    height, width = frame.shape
                    click_x = width / 2
                    click_y = temp_dict['TRAINER'] - (height / 10.11)
                    logger.debug('Click ' + str(click_x) + ' / ' + str(click_y))
                    self._communicator.click(click_x, click_y)
                    time.sleep(2)
                    return ScreenType.LOGINSELECT

        elif ScreenType(self.returntype) == ScreenType.FAILURE:
            self._pogoWindowManager.look_for_button(screenpath, 2.20, 3.01, self._communicator)
            time.sleep(2)
            return ScreenType.FAILURE

        elif ScreenType(self.returntype) == ScreenType.RETRY:
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


    def parseXML(self, xml):
        click_text = ('ZULASSEN', 'ALLOW', 'AUTORISER')
        xmlroot = ET.fromstring(xml)
        bounds: str = ""
        for item in xmlroot.iter('node'):
            if item.attrib['text'] in click_text:
                logger.debug("Found text {}", str(item.attrib['text']))
                bounds = item.attrib['bounds']
                logger.info("Bounds {}", str(item.attrib['bounds']))
                continue

        match = re.search(r'^\[(\d+),(\d+)\]\[(\d+),(\d+)\]$', bounds)

        click_x = int(match.group(1)) + ((int(match.group(3)) - int(match.group(1)))/2)
        click_y = int(match.group(2)) + ((int(match.group(4)) - int(match.group(2)))/2)
        logger.debug('Click ' + str(click_x) + ' / ' + str(click_y))

        return click_x, click_y


if __name__ == '__main__':
    screen = WordToScreenMatching(None, None, "test")
    screen.matchScreen("screenshot_tv_grant.jpg")
