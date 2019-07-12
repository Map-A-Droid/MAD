import cv2
import pytesseract
from pytesseract import Output
from enum import Enum
import numpy as np
import math
from utils.logging import logger

class ScreenType(Enum):
    UNDEFINED = -1
    RETURNING = 2
    LOGINSELECT = 3
    PTC = 4
    BIRTHDATE = 1
    FAILURE = 5
    RETRY = 6
    POGO = 99

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

class WordToScreenMatching(object):
    def __init__(self, communicator, pogoWindowManager, id):
        self._ScreenType: dict = {}
        self._id = id
        detect_ReturningScreen: list = ('ZURUCKKEHRENDER', 'ZURÜCKKEHRENDER', 'GAME', 'FREAK', 'SPIELER')
        detect_LoginScreen: list = ('TRAINER', 'CLUB', 'KIDS', 'Google', 'Facebook')
        detect_PTC: list = ('TRAINER-CLUB', 'Benutzername', 'Passwort')
        detect_FailureRetryScreen: list = ('TRY', 'DIFFERENT', 'ACCOUNT', 'Konto', 'anderes')
        detect_FailureLoginScreen: list = ('Authentifizierung', 'fehlgeschlagen')
        detect_Birthday: list = ('Geburtdatum')
        self._ScreenType[2] = detect_ReturningScreen
        self._ScreenType[3] = detect_LoginScreen
        self._ScreenType[4] = detect_PTC
        self._ScreenType[5] = detect_FailureLoginScreen
        self._ScreenType[6] = detect_FailureRetryScreen
        self._ScreenType[1] = detect_Birthday
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
        frame = cv2.imread(screenpath)
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        self.returntype: ScreenType = -1
        self._globaldict = pytesseract.image_to_data(frame, output_type=Output.DICT)
        n_boxes = len(self._globaldict['level'])
        for i in range(n_boxes):
            if self.returntype != -1: break
            if len(self._globaldict['text'][i]) > 3:
                for z in self._ScreenType:
                    if self._globaldict['text'][i] in self._ScreenType[z]:
                        self.returntype = z

        if ScreenType(self.returntype) != ScreenType.UNDEFINED:
            logger.info("Processing Screen: {}", str(ScreenType(self.returntype)))

        if ScreenType(self.returntype) == ScreenType.BIRTHDATE:
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
                        self._communicator.click(click_x, click_y)
                        self._communicator.touchandhold(click_x, click_y, click_x, click_y - 500)
                        self._communicator.touchandhold(click_x, click_y, click_x, click_y - 500)
                        self._communicator.click(click_x, click_y)
                        self._pogoWindowManager.look_for_button(screenpath, 2.20, 3.01, self._communicator)
                        return ScreenType.BIRTHDATE

        elif ScreenType(self.returntype) == ScreenType.RETURNING:

            ret, thresh = cv2.threshold(frame, 240, 255, cv2.THRESH_BINARY)
            frame[thresh == 255] = 0
            kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
            frame = cv2.erode(frame, kernel, iterations=1)
            frame = cv2.adaptiveThreshold(frame, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, \
                                          cv2.THRESH_BINARY, 11, 2)
            self._globaldict = pytesseract.image_to_data(frame, output_type=Output.DICT)
            n_boxes = len(self._globaldict['level'])
            for i in range(n_boxes):
                if 'ZURUCKKEHRENDER' in (self._globaldict['text'][i]):
                    (x, y, w, h) = (self._globaldict['left'][i], self._globaldict['top'][i],
                                    self._globaldict['width'][i], self._globaldict['height'][i])
                    click_x, click_y = x + w / 2, y + h / 2

                    self._communicator.click(click_x, click_y)

                    return ScreenType.RETURNING

        elif ScreenType(self.returntype) == ScreenType.LOGINSELECT:
            n_boxes = len(self._globaldict['level'])
            for i in range(n_boxes):
                if 'Google' in (self._globaldict['text'][i]):
                    (x, y, w, h) = (self._globaldict['left'][i], self._globaldict['top'][i],
                                    self._globaldict['width'][i], self._globaldict['height'][i])
                    click_x, click_y = x + w / 2, y + h / 2

                    self._communicator.click(click_x, click_y)

                    return ScreenType.LOGINSELECT

        elif ScreenType(self.returntype) == ScreenType.FAILURE:
            self._pogoWindowManager.look_for_button(screenpath, 2.20, 3.01, self._communicator)

            return ScreenType.FAILURE

        elif ScreenType(self.returntype) == ScreenType.RETRY:
            n_boxes = len(self._globaldict['level'])
            for i in range(n_boxes):
                if 'DIFFERENT' in (self._globaldict['text'][i]):
                    (x, y, w, h) = (self._globaldict['left'][i], self._globaldict['top'][i],
                                    self._globaldict['width'][i], self._globaldict['height'][i])
                    click_x, click_y = x + w / 2, y + h / 2

                    self._communicator.click(click_x, click_y)

            return ScreenType.RETRY

        else:
            return ScreenType.POGO


if __name__ == '__main__':
    screen = WordToScreenMatching(None, None, "test")
    screen.matchScreen("screenshot_m7_bith.jpg")
