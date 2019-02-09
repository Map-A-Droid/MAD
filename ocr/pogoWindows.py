# -*- coding: utf-8 -*-
import collections
import logging
import math
import os
import os.path
import time

import cv2
import numpy as np
from PIL import Image

Coordinate = collections.namedtuple("Coordinate", ['x', 'y'])
Bounds = collections.namedtuple("Bounds", ['top', 'bottom', 'left', 'right'])

log = logging.getLogger(__name__)


class PogoWindows:
    def __init__(self, communicator, tempDirPath):
        self.communicator = communicator
        if not os.path.exists(tempDirPath):
            os.makedirs(tempDirPath)
            log.info('PogoWindows: Temp directory created')
        self.tempDirPath = tempDirPath

    def __mostPresentColour(self, filename, maxColours):
        img = Image.open(filename)
        # put a higher value if there are many colors in your image
        colors = img.getcolors(maxColours)
        max_occurence, most_present = 0, 0
        try:
            for c in colors:
                if c[0] > max_occurence:
                    (max_occurence, most_present) = c
            return most_present
        except TypeError:
            return None

    def isGpsSignalLost(self, filename, hash):
        if not os.path.isfile(filename):
            log.error("isGpsSignalLost: %s does not exist" % str(filename))
            return None

        log.debug("isGpsSignalLost: checking for red bar")
        try:
            col = cv2.imread(filename)
        except:
            log.error("Screenshot corrupted :(")
            return True

        if col is None:
            log.error("Screenshot corrupted :(")
            return True

        width, height, _ = col.shape

        gpsError = col[0:int(math.floor(height / 7)), 0:width]

        tempPathColoured = self.tempDirPath + "/" + str(hash) + "_gpsError.png"
        cv2.imwrite(tempPathColoured, gpsError)

        col = Image.open(tempPathColoured)
        width, height = col.size

        # check for the colour of the GPS error
        if self.__mostPresentColour(tempPathColoured, width * height) == (240, 75, 95):
            return True
        else:
            return False

    def __readCircleCount(self, filename, hash, ratio, xcord=False, crop=False, click=False, canny=False, secondratio=False):
        log.debug("__readCircleCount: Reading circles")

        try:
            screenshotRead = cv2.imread(filename)
        except:
            log.error("Screenshot corrupted :(")
            return -1

        if screenshotRead is None:
            log.error("Screenshot corrupted :(")
            return -1

        height, width, _ = screenshotRead.shape

        if crop:
            screenshotRead = screenshotRead[int(height) - int(round(height / 4.5)):int(height),
                                            round(int(width) / 2) - round(int(width) / 8):round(int(width) / 2) + round(
                int(width) / 8)]

        log.debug("__readCircleCount: Determined screenshot scale: " +
                  str(height) + " x " + str(width))
        gray = cv2.cvtColor(screenshotRead, cv2.COLOR_BGR2GRAY)
        # detect circles in the image

        if not secondratio:
            radMin = int((width / float(ratio) - 3) / 2)
            radMax = int((width / float(ratio) + 3) / 2)
        else:
            radMin = int((width / float(ratio) - 3) / 2)
            radMax = int((width / float(secondratio) + 3) / 2)
        if canny:
            gray = cv2.GaussianBlur(gray, (3, 3), 0)
            gray = cv2.Canny(gray, 100, 50, apertureSize=3)

        log.debug("__readCircleCount: Detect radius of circle: Min " +
                  str(radMin) + " Max " + str(radMax))
        circles = cv2.HoughCircles(gray, cv2.HOUGH_GRADIENT, 1, width / 8, param1=100, param2=15, minRadius=radMin,
                                   maxRadius=radMax)
        circle = 0
        # ensure at least some circles were found
        if circles is not None:
            # convert the (x, y) coordinates and radius of the circles to integers
            circles = np.round(circles[0, :]).astype("int")
            # loop over the (x, y) coordinates and radius of the circles
            for (x, y, r) in circles:

                if not xcord:
                    circle += 1
                    if click:
                        log.debug('__readCircleCount: found Circle - click it')
                        self.communicator.click(
                            width / 2, ((int(height) - int(height / 4.5))) + y)
                        time.sleep(2)
                else:
                    if x >= (width / 2) - 100 and x <= (width / 2) + 100 and y >= (height - (height / 3)):
                        circle += 1
                        if click:
                            log.debug(
                                '__readCircleCount: found Circle - click on: it')
                            self.communicator.click(
                                width / 2, ((int(height) - int(height / 4.5))) + y)
                            time.sleep(2)

            log.debug(
                "__readCircleCount: Determined screenshot to have " + str(circle) + " Circle.")
            return circle
        else:
            log.debug("__readCircleCount: Determined screenshot to have 0 Circle")
            return -1

    def __readCircleCords(self, filename, hash, ratio, crop=False, canny=False):
        log.debug("__readCircleCords: Reading circlescords")

        try:
            screenshotRead = cv2.imread(filename)
        except:
            log.error("Screenshot corrupted :(")
            return False

        if screenshotRead is None:
            log.error("Screenshot corrupted :(")
            return False

        height, width, _ = screenshotRead.shape

        if crop:
            screenshotRead = screenshotRead[int(height) - int(height / 5):int(height),
                                            int(width) / 2 - int(width) / 8:int(width) / 2 + int(width) / 8]

        log.debug("__readCircleCords: Determined screenshot scale: " +
                  str(height) + " x " + str(width))
        gray = cv2.cvtColor(screenshotRead, cv2.COLOR_BGR2GRAY)
        # detect circles in the image

        radMin = int((width / float(ratio) - 3) / 2)
        radMax = int((width / float(ratio) + 3) / 2)

        if canny:
            gray = cv2.GaussianBlur(gray, (3, 3), 0)
            gray = cv2.Canny(gray, 100, 50, apertureSize=3)

        log.debug("__readCircleCords: Detect radius of circle: Min " +
                  str(radMin) + " Max " + str(radMax))
        circles = cv2.HoughCircles(gray, cv2.HOUGH_GRADIENT, 1, width / 8, param1=100, param2=15, minRadius=radMin,
                                   maxRadius=radMax)
        circle = 0
        # ensure at least some circles were found
        if circles is not None:
            # convert the (x, y) coordinates and radius of the circles to integers
            circles = np.round(circles[0, :]).astype("int")
            # loop over the (x, y) coordinates and radius of the circles
            for (x, y, r) in circles:
                log.debug("__readCircleCords: Found Circle x: %s y: %s" % (
                    str(width / 2), str((int(height) - int(height / 5)) + y)))
                return True, width / 2, (int(height) - int(height / 5)) + y, height, width
        else:
            log.debug("__readCircleCords: Found no Circle")
            return False, 0, 0, 0, 0

    def readRaidCircles(self, filename, hash):
        log.debug("readCircles: Reading circles")
        if not self.readAmountOfRaidsCircle(filename, hash):
            # no raidcount (orange circle) present...
            return 0

        circle = self.__readCircleCount(filename, hash, 4.7)

        if circle > 6:
            circle = 6

        if circle > 0:
            log.debug("readCircles: Determined screenshot to have " +
                      str(circle) + " Circle.")
            return circle

        log.debug(
            "readCircles: Determined screenshot to not contain raidcircles, but a raidcount!")
        return -1

    def lookForButton(self, filename, ratiomin, ratiomax):
        log.debug("lookForButton: Reading lines")
        disToMiddleMin = None
        try:
            screenshotRead = cv2.imread(filename)
            gray = cv2.cvtColor(screenshotRead, cv2.COLOR_BGR2GRAY)
        except:
            log.error("Screenshot corrupted :(")
            return False

        if screenshotRead is None:
            log.error("Screenshot corrupted :(")
            return False

        allowRatio = [1.60, 1.05, 2.20, 3.01, 2.32]

        height, width, _ = screenshotRead.shape
        _widthold = float(width)
        log.debug("lookForButton: Determined screenshot scale: " +
                  str(height) + " x " + str(width))

        # resize for better line quality
        # gray = cv2.resize(gray, (0,0), fx=width*0.001, fy=width*0.001)
        height, width = gray.shape
        faktor = width / _widthold

        gray = cv2.GaussianBlur(gray, (3, 3), 0)
        edges = cv2.Canny(gray, 50, 200, apertureSize=3)
        # checking for all possible button lines

        maxLineLength = (width / ratiomin) + (width * 0.18)
        log.debug("lookForButton: MaxLineLength:" + str(maxLineLength))
        minLineLength = (width / ratiomax) - (width * 0.02)
        log.debug("lookForButton: MinLineLength:" + str(minLineLength))

        kernel = np.ones((2, 2), np.uint8)
        edges = cv2.morphologyEx(edges, cv2.MORPH_GRADIENT, kernel)

        maxLineGap = 50
        lineCount = 0
        lines = []
        _x = 0
        _y = height
        lines = cv2.HoughLinesP(edges, rho=1, theta=math.pi / 180, threshold=70, minLineLength=minLineLength,
                                maxLineGap=2)
        if lines is None:
            return False

        for line in lines:
            for x1, y1, x2, y2 in line:

                if y1 == y2 and (x2 - x1 <= maxLineLength) and (x2 - x1 >= minLineLength) and y1 > height / 2:

                    lineCount += 1
                    __y = y2
                    __x1 = x1
                    __x2 = x2
                    if __y < _y:
                        _y = __y
                        _x1 = __x1
                        _x2 = __x2

                    log.debug("lookForButton: Found Buttonline Nr. " + str(lineCount) + " - Line lenght: " + str(
                        x2 - x1) + "px Coords - X: " + str(x1) + " " + str(x2) + " Y: " + str(y1) + " " + str(y2))

        if 1 < lineCount <= 6:
            # recalculate click area for real resolution
            click_x = int(((width - _x2) + ((_x2 - _x1) / 2)) /
                          round(faktor, 2))
            click_y = int(_y / round(faktor, 2) + height * 0.03)
            log.debug('lookForButton: found Button - click on it')
            self.communicator.click(click_x, click_y)
            time.sleep(4)
            return True

        elif lineCount > 6:
            log.debug('lookForButton: found to much Buttons :) - close it')
            self.communicator.click(
                int(width - (width / 7.2)), int(height - (height / 12.19)))
            time.sleep(4)

            return True

        log.debug('lookForButton: did not found any Button')
        return False

    def __checkRaidLine(self, filename, hash, leftSide=False, clickinvers=False):
        log.debug("__checkRaidLine: Reading lines")
        if leftSide:
            log.debug("__checkRaidLine: Check nearby open ")
        try:
            screenshotRead = cv2.imread(filename)
        except:
            log.error("Screenshot corrupted :(")
            return False
        if screenshotRead is None:
            log.error("Screenshot corrupted :(")
            return False

        if self.__readCircleCount(os.path.join('', filename), hash, float(11), xcord=False, crop=True, click=False,
                                  canny=True) == -1:
            log.debug("__checkRaidLine: Not active")
            return False

        height, width, _ = screenshotRead.shape
        screenshotRead = screenshotRead[int(height / 2) - int(height / 3):int(height / 2) + int(height / 3),
                                        int(0):int(width)]
        gray = cv2.cvtColor(screenshotRead, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (5, 5), 0)
        log.debug("__checkRaidLine: Determined screenshot scale: " +
                  str(height) + " x " + str(width))
        edges = cv2.Canny(gray, 50, 150, apertureSize=3)
        maxLineLength = width / 3.30 + width * 0.03
        log.debug("__checkRaidLine: MaxLineLength:" + str(maxLineLength))
        minLineLength = width / 6.35 - width * 0.03
        log.debug("__checkRaidLine: MinLineLength:" + str(minLineLength))
        maxLineGap = 50

        lines = cv2.HoughLinesP(edges, rho=1, theta=math.pi / 180, threshold=70, minLineLength=minLineLength,
                                maxLineGap=2)
        if lines is None:
            return False
        for line in lines:
            for x1, y1, x2, y2 in line:
                if not leftSide:
                    if y1 == y2 and (x2 - x1 <= maxLineLength) and (
                            x2 - x1 >= minLineLength) and x1 > width / 2 and x2 > width / 2 and y1 < (height / 2):
                        log.debug("__checkRaidLine: Raid-tab is active - Line lenght: " + str(
                            x2 - x1) + "px Coords - X: " + str(x1) + " " + str(x2) + " Y: " + str(y1) + " " + str(y2))
                        return True
                    # else: log.debug("__checkRaidLine: Raid-tab is not active - Line lenght: " + str(x2-x1) + "px
                    # Coords - X: " + str(x1) + " " + str(x2) + " Y: " + str(y1) + " " + str(y2)) return False
                else:
                    if y1 == y2 and (x2 - x1 <= maxLineLength) and (
                            x2 - x1 >= minLineLength) and ((x1 < width / 2 and x2 < width / 2) or (x1 < width / 2 and x2 > width / 2)) and y1 < (height / 2):
                        log.debug(
                            "__checkRaidLine: Nearby is active - but not Raid-Tab")
                        if clickinvers:
                            xRaidTab = int(width - (x2 - x1))
                            yRaidTab = int(
                                (int(height / 2) - int(height / 3) + y1) * 0.9)
                            log.debug('__checkRaidLine: open Raid-Tab')
                            self.communicator.click(xRaidTab, yRaidTab)
                            time.sleep(3)
                        return True
                    # else:
                    # log.debug("__checkRaidLine: Nearby not active - but maybe Raid-tab")
                    # return False
        log.debug("__checkRaidLine: Not active")
        return False

    def readAmountOfRaidsCircle(self, filename, hash):
        if not os.path.isfile(filename):
            return None

        log.debug("readAmountOfRaidsCircle: Cropping circle")

        try:
            image = cv2.imread(filename)
        except:
            log.error("Screenshot corrupted :(")
            return False
        if image is None:
            log.error("Screenshot corrupted :(")
            return False

        height, width, _ = image.shape
        image = image[int(height / 2 - (height / 3))                      :int(height / 2 + (height / 3)), 0:int(width)]
        cv2.imwrite(os.path.join(self.tempDirPath, str(
            hash) + '_AmountOfRaids.jpg'), image)

        if self.__readCircleCount(os.path.join(self.tempDirPath, str(hash) + '_AmountOfRaids.jpg'), hash, 18) > 0:
            log.info(
                "readAmountOfRaidsCircle: Raidcircle found, assuming raids nearby")
            os.remove(os.path.join(self.tempDirPath,
                                   str(hash) + '_AmountOfRaids.jpg'))
            return True
        else:
            log.info(
                "readAmountOfRaidsCircle: No raidcircle found, assuming no raids nearby")
            os.remove(os.path.join(self.tempDirPath,
                                   str(hash) + '_AmountOfRaids.jpg'))
            return False

    # assumes we are on the general view of the game
    def checkRaidscreen(self, filename, hash):
        log.debug("checkRaidscreen: Checking if RAID is present (nearby tab)")

        if self.__checkRaidLine(filename, hash):
            log.debug('checkRaidscreen: RAID-tab found')
            return True
        if self.__checkRaidLine(filename, hash, True):
            log.debug('checkRaidscreen: RAID-tab not activated')
            return False

        log.debug('checkRaidscreen: nearby not found')
        # log.warning('checkRaidscreen: Could not locate RAID-tab')
        return False

    def checkNearby(self, filename, hash):
        try:
            screenshotRead = cv2.imread(filename)
        except:
            log.error("Screenshot corrupted :(")
            return False
        if screenshotRead is None:
            log.error("Screenshot corrupted :(")
            return False

        if self.__checkRaidLine(filename, hash):
            log.info('Nearby already open')
            return True

        if self.__checkRaidLine(filename, hash, leftSide=True, clickinvers=True):
            log.info('Raidscreen not running but nearby open')
            return False

        height, width, _ = screenshotRead.shape

        log.info('Raidscreen not running...')
        self.communicator.click(
            int(width - (width / 7.2)), int(height - (height / 12.19)))
        time.sleep(4)
        return False

    def __checkClosePresent(self, filename, hash, radiusratio=12, Xcord=True):
        if not os.path.isfile(filename):
            log.warning("__checkClosePresent: %s does not exist" %
                        str(filename))
            return False

        try:
            image = cv2.imread(filename)
            height, width, _ = image.shape
        except:
            log.error("Screenshot corrupted :(")
            return False

        cv2.imwrite(os.path.join(self.tempDirPath,
                                 str(hash) + '_exitcircle.jpg'), image)

        if self.__readCircleCount(os.path.join(self.tempDirPath, str(hash) + '_exitcircle.jpg'), hash,
                                  float(radiusratio), xcord=False, crop=True, click=True, canny=True) > 0:
            return True

    # checks for X button on any screen... could kill raidscreen, handle properly
    def checkCloseExceptNearbyButton(self, filename, hash, closeraid=False):
        log.debug("checkCloseExceptNearbyButton: Checking close except nearby with: file %s, hash %s" % (
            filename, hash))
        try:
            screenshotRead = cv2.imread(filename)
        except:
            log.error("Screenshot corrupted :(")
            log.debug("checkCloseExceptNearbyButton: Screenshot corrupted...")
            return False
        if screenshotRead is None:
            log.error("checkCloseExceptNearbyButton: Screenshot corrupted :(")
            return False

        if not closeraid:
            log.debug("checkCloseExceptNearbyButton: Raid is not to be closed...")
            if (not os.path.isfile(filename)
                    or self.__checkRaidLine(filename, hash)
                    or self.__checkRaidLine(filename, hash, True)):
                # file not found or raid tab present
                log.debug(
                    "checkCloseExceptNearbyButton: Not checking for close button (X). Input wrong OR nearby window open")
                return False
        log.debug(
            "checkCloseExceptNearbyButton: Checking for close button (X). Input wrong OR nearby window open")

        if self.__checkClosePresent(filename, hash, 10, True):
            log.debug("Found close button (X). Closing the window - Ratio: 10")
            return True
        if self.__checkClosePresent(filename, hash, 11, True):
            log.debug("Found close button (X). Closing the window - Ratio: 11")
            return True
        elif self.__checkClosePresent(filename, hash, 12, True):
            log.debug("Found close button (X). Closing the window - Ratio: 12")
            return True
        elif self.__checkClosePresent(filename, hash, 14, True):
            log.debug("Found close button (X). Closing the window - Ratio: 14")
            return True
        elif self.__checkClosePresent(filename, hash, 13, True):
            log.debug("Found close button (X). Closing the window - Ratio: 13")
            return True
        else:
            log.debug("Could not find close button (X).")
            return False

    def checkpogomainscreen(self, filename, hash):
        log.debug("checkpogomainscreen: Checking close except nearby with: file %s, hash %s" % (
            filename, hash))
        try:
            screenshotRead = cv2.imread(filename)
        except:
            log.error("Screenshot corrupted :(")
            log.debug("checkCloseExceptNearbyButton: Screenshot corrupted...")
            return False
        if screenshotRead is None:
            log.error("checkCloseExceptNearbyButton: Screenshot corrupted :(")
            return False
            # 7.5
        if self.__readCircleCount(filename, hash,
                                  float(8.5), xcord=False, crop=True, click=False, canny=True, secondratio=float(7.5)) > 0:
            log.info("Found Pokeball.")
            return True
        return False

    def checkCloseButton(self, filename, hash):
        log.debug(
            "checkCloseButton: Checking close with: file %s, hash %s" % (filename, hash))
        try:
            screenshotRead = cv2.imread(filename)
        except:
            log.error("Screenshot corrupted :(")
            log.debug("checkCloseButton: Screenshot corrupted...")
            return False
        if screenshotRead is None:
            log.error("checkCloseButton: Screenshot corrupted :(")
            return False

        if self.__readCircleCount(filename, hash,
                                  float(7.7), xcord=False, crop=True, click=True, canny=True) > 0:
            log.debug("Found close button (X). Closing the window - Ratio: 10")
            return True

        if self.__checkClosePresent(filename, hash, 10, False):
            log.debug("Found close button (X). Closing the window - Ratio: 10")
            return True
        if self.__checkClosePresent(filename, hash, 8, False):
            log.debug("Found close button (X). Closing the window - Ratio: 8")
            return True
        elif self.__checkClosePresent(filename, hash, 12, False):
            log.debug("Found close button (X). Closing the window - Ratio: 12")
            return True
        elif self.__checkClosePresent(filename, hash, 14, False):
            log.debug("Found close button (X). Closing the window - Ratio: 14")
            return True
        elif self.__checkClosePresent(filename, hash, 13, False):
            log.debug("Found close button (X). Closing the window - Ratio: 13")
            return True
        else:
            log.debug("Could not find close button (X).")
            return False
