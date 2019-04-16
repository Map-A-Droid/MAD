# -*- coding: utf-8 -*-
import collections
import math
import os
import os.path
import time

import cv2
# from numpy import round, ones, uint8
# from tinynumpy import tinynumpy as np
from loguru import logger
import numpy as np
from PIL import Image
import pytesseract


Coordinate = collections.namedtuple("Coordinate", ['x', 'y'])
Bounds = collections.namedtuple("Bounds", ['top', 'bottom', 'left', 'right'])


class PogoWindows:
    def __init__(self, tempDirPath):
        # self.communicator = communicator
        if not os.path.exists(tempDirPath):
            os.makedirs(tempDirPath)
            logger.info('PogoWindows: Temp directory created')
        self.tempDirPath = tempDirPath

    def __mostPresentColour(self, filename, maxColours):
        img = Image.open(filename)
        colors = img.getcolors(maxColours)  # put a higher value if there are many colors in your image
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
            logger.error("isGpsSignalLost: {} does not exist", str(filename))
            return None

        logger.debug("isGpsSignalLost: checking for red bar")
        try:
            col = cv2.imread(filename)
        except Exception:
            logger.error("Screenshot corrupted :(")
            return True

        if col is None:
            logger.error("Screenshot corrupted :(")
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

    def __readCircleCount(self, filename, hash, ratio, communicator, xcord=False, crop=False, click=False, canny=False,
                          secondratio=False):
        logger.debug("__readCircleCount: Reading circles")

        try:
            screenshotRead = cv2.imread(filename)
        except Exception:
            logger.error("Screenshot corrupted :(")
            return -1

        if screenshotRead is None:
            logger.error("Screenshot corrupted :(")
            return -1

        height, width, _ = screenshotRead.shape

        if crop:
            screenshotRead = screenshotRead[int(height) - int(int(height / 4.5)):int(height),
                                            int(int(width) / 2) - int(int(width) / 8):int(int(width) / 2) + int(
                                            int(width) / 8)]

        logger.debug("__readCircleCount: Determined screenshot scale: " + str(height) + " x " + str(width))
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

        logger.debug("__readCircleCount: Detect radius of circle: Min " + str(radMin) + " Max " + str(radMax))
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
                        logger.debug('__readCircleCount: found Circle - click it')
                        communicator.click(width / 2, ((int(height) - int(height / 4.5))) + y)
                        time.sleep(2)
                else:
                    if x >= (width / 2) - 100 and x <= (width / 2) + 100 and y >= (height - (height / 3)):
                        circle += 1
                        if click:
                            logger.debug('__readCircleCount: found Circle - click on: it')
                            communicator.click(width / 2, ((int(height) - int(height / 4.5))) + y)
                            time.sleep(2)

            logger.debug("__readCircleCount: Determined screenshot to have " + str(circle) + " Circle.")
            return circle
        else:
            logger.debug("__readCircleCount: Determined screenshot to have 0 Circle")
            return -1

    def __readCircleCords(self, filename, hash, ratio, crop=False, canny=False):
        logger.debug("__readCircleCords: Reading circlescords")

        try:
            screenshotRead = cv2.imread(filename)
        except Exception:
            logger.error("Screenshot corrupted :(")
            return False

        if screenshotRead is None:
            logger.error("Screenshot corrupted :(")
            return False

        height, width, _ = screenshotRead.shape

        if crop:
            screenshotRead = screenshotRead[int(height) - int(height / 5):int(height),
                                            int(width) / 2 - int(width) / 8:int(width) / 2 + int(width) / 8]

        logger.debug("__readCircleCords: Determined screenshot scale: " + str(height) + " x " + str(width))
        gray = cv2.cvtColor(screenshotRead, cv2.COLOR_BGR2GRAY)
        # detect circles in the image

        radMin = int((width / float(ratio) - 3) / 2)
        radMax = int((width / float(ratio) + 3) / 2)

        if canny:
            gray = cv2.GaussianBlur(gray, (3, 3), 0)
            gray = cv2.Canny(gray, 100, 50, apertureSize=3)

        logger.debug("__readCircleCords: Detect radius of circle: Min " + str(radMin) + " Max " + str(radMax))
        circles = cv2.HoughCircles(gray, cv2.HOUGH_GRADIENT, 1, width / 8, param1=100, param2=15, minRadius=radMin,
                                   maxRadius=radMax)
        circle = 0
        # ensure at least some circles were found
        if circles is not None:
            # convert the (x, y) coordinates and radius of the circles to integers
            circles = np.round(circles[0, :]).astype("int")
            # loop over the (x, y) coordinates and radius of the circles
            for (x, y, r) in circles:
                logger.debug("__readCircleCords: Found Circle x: {} y: {}", str(width / 2), str((int(height) - int(height / 5)) + y))
                return True, width / 2, (int(height) - int(height / 5)) + y, height, width
        else:
            logger.debug("__readCircleCords: Found no Circle")
            return False, 0, 0, 0, 0

    def readRaidCircles(self, filename, hash, commuicator):
        logger.debug("readCircles: Reading circles")
        if not self.readAmountOfRaidsCircle(filename, hash, commuicator):
            # no raidcount (orange circle) present...
            return 0

        circle = self.__readCircleCount(filename, hash, 4.7, commuicator)

        if circle > 6:
            circle = 6

        if circle > 0:
            logger.debug("readCircles: Determined screenshot to have " + str(circle) + " Circle.")
            return circle

        logger.debug("readCircles: Determined screenshot to not contain raidcircles, but a raidcount!")
        return -1

    def lookForButton(self, filename, ratiomin, ratiomax, communicator):
        logger.debug("lookForButton: Reading lines")
        disToMiddleMin = None
        try:
            screenshotRead = cv2.imread(filename)
            gray = cv2.cvtColor(screenshotRead, cv2.COLOR_BGR2GRAY)
        except:
            logger.error("Screenshot corrupted :(")
            return False

        if screenshotRead is None:
            logger.error("Screenshot corrupted :(")
            return False

        allowRatio = [1.60, 1.05, 2.20, 3.01, 2.32]

        height, width, _ = screenshotRead.shape
        _widthold = float(width)
        logger.debug("lookForButton: Determined screenshot scale: " + str(height) + " x " + str(width))

        # resize for better line quality
        # gray = cv2.resize(gray, (0,0), fx=width*0.001, fy=width*0.001)
        height, width = gray.shape
        faktor = width / _widthold

        gray = cv2.GaussianBlur(gray, (3, 3), 0)
        edges = cv2.Canny(gray, 50, 200, apertureSize=3)
        # checking for all possible button lines

        maxLineLength = (width / ratiomin) + (width * 0.18)
        logger.debug("lookForButton: MaxLineLength:" + str(maxLineLength))
        minLineLength = (width / ratiomax) - (width * 0.02)
        logger.debug("lookForButton: MinLineLength:" + str(minLineLength))

        kernel = np.ones((2, 2), np.uint8)
        # kernel = np.zeros(shape=(2, 2), dtype=np.uint8)
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

                if y1 == y2 and x2 - x1 <= maxLineLength and x2 - x1 >= minLineLength and y1 > height / 2 \
                        and (x2-x1)/2 + x1 < width/2+100 and (x2 - x1)/2+x1 > width/2-100:

                    lineCount += 1
                    __y = y2
                    __x1 = x1
                    __x2 = x2
                    if __y < _y:
                        _y = __y
                        _x1 = __x1
                        _x2 = __x2

                    logger.debug("lookForButton: Found Buttonline Nr. " + str(lineCount) + " - Line lenght: " + str(
                        x2 - x1) + "px Coords - X: " + str(x1) + " " + str(x2) + " Y: " + str(y1) + " " + str(y2))

        if 1 < lineCount <= 6:
            # recalculate click area for real resolution
            click_x = int(((width - _x2) + ((_x2 - _x1) / 2)) / round(faktor, 2))
            click_y = int(_y / round(faktor, 2) + height * 0.03)
            logger.debug('lookForButton: found Button - click on it')
            communicator.click(click_x, click_y)
            time.sleep(4)
            return True

        elif lineCount > 6:
            logger.debug('lookForButton: found to much Buttons :) - close it')
            communicator.click(int(width - (width / 7.2)), int(height - (height / 12.19)))
            time.sleep(4)

            return True

        logger.debug('lookForButton: did not found any Button')
        return False

    def __checkRaidLine(self, filename, hash, communicator, leftSide=False, clickinvers=False):
        logger.debug("__checkRaidLine: Reading lines")
        if leftSide:
            logger.debug("__checkRaidLine: Check nearby open ")
        try:
            screenshotRead = cv2.imread(filename)
        except Exception:
            logger.error("Screenshot corrupted :(")
            return False
        if screenshotRead is None:
            logger.error("Screenshot corrupted :(")
            return False

        if self.__readCircleCount(os.path.join('', filename), hash, float(11), communicator, xcord=False, crop=True,
                                  click=False, canny=True) == -1:
            logger.debug("__checkRaidLine: Not active")
            return False

        height, width, _ = screenshotRead.shape
        screenshotRead = screenshotRead[int(height / 2) - int(height / 3):int(height / 2) + int(height / 3),
                                        int(0):int(width)]
        gray = cv2.cvtColor(screenshotRead, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (5, 5), 0)
        logger.debug("__checkRaidLine: Determined screenshot scale: " + str(height) + " x " + str(width))
        edges = cv2.Canny(gray, 50, 150, apertureSize=3)
        maxLineLength = width / 3.30 + width * 0.03
        logger.debug("__checkRaidLine: MaxLineLength:" + str(maxLineLength))
        minLineLength = width / 6.35 - width * 0.03
        logger.debug("__checkRaidLine: MinLineLength:" + str(minLineLength))
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
                        logger.debug("__checkRaidLine: Raid-tab is active - Line lenght: " + str(
                            x2 - x1) + "px Coords - X: " + str(x1) + " " + str(x2) + " Y: " + str(y1) + " " + str(y2))
                        return True
                    # else: logger.debug("__checkRaidLine: Raid-tab is not active - Line lenght: " + str(x2-x1) + "px
                    # Coords - X: " + str(x1) + " " + str(x2) + " Y: " + str(y1) + " " + str(y2)) return False
                else:
                    if y1 == y2 and (x2 - x1 <= maxLineLength) and (
                            x2 - x1 >= minLineLength) and ((x1 < width / 2 and x2 < width / 2) or (x1 < width / 2 and x2 > width / 2)) and y1 < (height / 2):
                        logger.debug("__checkRaidLine: Nearby is active - but not Raid-Tab")
                        if clickinvers:
                            xRaidTab = int(width - (x2 - x1))
                            yRaidTab = int((int(height / 2) - int(height / 3) + y1) * 0.9)
                            logger.debug('__checkRaidLine: open Raid-Tab')
                            communicator.click(xRaidTab, yRaidTab)
                            time.sleep(3)
                        return True
                    # else:
                    # logger.debug("__checkRaidLine: Nearby not active - but maybe Raid-tab")
                    # return False
        logger.debug("__checkRaidLine: Not active")
        return False

    def readAmountOfRaidsCircle(self, filename, hash, communicator):
        if not os.path.isfile(filename):
            return None

        logger.debug("readAmountOfRaidsCircle: Cropping circle")

        try:
            image = cv2.imread(filename)
        except Exception:
            logger.error("Screenshot corrupted :(")
            return False
        if image is None:
            logger.error("Screenshot corrupted :(")
            return False

        height, width, _ = image.shape
        image = image[int(height / 2 - (height / 3)):int(height / 2 + (height / 3)), 0:int(width)]
        cv2.imwrite(os.path.join(self.tempDirPath, str(hash) + '_AmountOfRaids.jpg'), image)

        if self.__readCircleCount(os.path.join(self.tempDirPath, str(hash) + '_AmountOfRaids.jpg'), hash, 18,
                                  communicator) > 0:
            logger.info("readAmountOfRaidsCircle: Raidcircle found, assuming raids nearby")
            os.remove(os.path.join(self.tempDirPath, str(hash) + '_AmountOfRaids.jpg'))
            return True
        else:
            logger.info("readAmountOfRaidsCircle: No raidcircle found, assuming no raids nearby")
            os.remove(os.path.join(self.tempDirPath, str(hash) + '_AmountOfRaids.jpg'))
            return False

    # assumes we are on the general view of the game
    def checkRaidscreen(self, filename, hash, communicator):
        logger.debug("checkRaidscreen: Checking if RAID is present (nearby tab)")

        if self.__checkRaidLine(filename, hash, communicator):
            logger.debug('checkRaidscreen: RAID-tab found')
            return True
        if self.__checkRaidLine(filename, hash, communicator, True):
            logger.debug('checkRaidscreen: RAID-tab not activated')
            return False

        logger.debug('checkRaidscreen: nearby not found')
        # logger.warning('checkRaidscreen: Could not locate RAID-tab')
        return False

    def checkNearby(self, filename, hash, communicator):
        try:
            screenshotRead = cv2.imread(filename)
        except Exception:
            logger.error("Screenshot corrupted :(")
            return False
        if screenshotRead is None:
            logger.error("Screenshot corrupted :(")
            return False

        if self.__checkRaidLine(filename, hash, communicator):
            logger.info('Nearby already open')
            return True

        if self.__checkRaidLine(filename, hash, communicator, leftSide=True, clickinvers=True):
            logger.info('Raidscreen not running but nearby open')
            return False

        height, width, _ = screenshotRead.shape

        logger.info('Raidscreen not running...')
        communicator.click(int(width - (width / 7.2)), int(height - (height / 12.19)))
        time.sleep(4)
        return False

    def __checkClosePresent(self, filename, hash, communicator,  radiusratio=12, Xcord=True):
        if not os.path.isfile(filename):
            logger.warning("__checkClosePresent: {} does not exist", str(filename))
            return False

        try:
            image = cv2.imread(filename)
            height, width, _ = image.shape
        except:
            logger.error("Screenshot corrupted :(")
            return False

        cv2.imwrite(os.path.join(self.tempDirPath, str(hash) + '_exitcircle.jpg'), image)

        if self.__readCircleCount(os.path.join(self.tempDirPath, str(hash) + '_exitcircle.jpg'), hash,
                                  float(radiusratio), communicator, xcord=False, crop=True, click=True, canny=True) > 0:
            return True

    # checks for X button on any screen... could kill raidscreen, handle properly
    def checkCloseExceptNearbyButton(self, filename, hash, communicator, closeraid=False):
        logger.debug("checkCloseExceptNearbyButton: Checking close except nearby with: file {}, hash {}", filename, hash)
        try:
            screenshotRead = cv2.imread(filename)
        except:
            logger.error("Screenshot corrupted :(")
            logger.debug("checkCloseExceptNearbyButton: Screenshot corrupted...")
            return False
        if screenshotRead is None:
            logger.error("checkCloseExceptNearbyButton: Screenshot corrupted :(")
            return False

        if not closeraid:
            logger.debug("checkCloseExceptNearbyButton: Raid is not to be closed...")
            if (not os.path.isfile(filename)
                    or self.__checkRaidLine(filename, hash, communicator)
                    or self.__checkRaidLine(filename, hash, communicator, True)):
                # file not found or raid tab present
                logger.debug(
                    "checkCloseExceptNearbyButton: Not checking for close button (X). Input wrong OR nearby window open")
                return False
        logger.debug("checkCloseExceptNearbyButton: Checking for close button (X). Input wrong OR nearby window open")

        if self.__checkClosePresent(filename, hash, communicator, 10, True):
            logger.debug("Found close button (X). Closing the window - Ratio: 10")
            return True
        if self.__checkClosePresent(filename, hash, communicator, 11, True):
            logger.debug("Found close button (X). Closing the window - Ratio: 11")
            return True
        elif self.__checkClosePresent(filename, hash, communicator, 12, True):
            logger.debug("Found close button (X). Closing the window - Ratio: 12")
            return True
        elif self.__checkClosePresent(filename, hash, communicator, 14, True):
            logger.debug("Found close button (X). Closing the window - Ratio: 14")
            return True
        elif self.__checkClosePresent(filename, hash, communicator, 13, True):
            logger.debug("Found close button (X). Closing the window - Ratio: 13")
            return True
        else:
            logger.debug("Could not find close button (X).")
            return False

    def get_inventory_text(self, filename, hash, x1, x2, y1, y2):
        screenshotRead = cv2.imread(filename)
        tempPathitem = self.tempDirPath + "/" + str(hash) + "_inventory.png"
        h = x1 - x2
        w = y1 - y2
        gray = cv2.cvtColor(screenshotRead, cv2.COLOR_BGR2GRAY)
        gray = gray[int(y2):(int(y2) + int(w)), int(x2):(int(x2) + int(h))]
        cv2.imwrite(tempPathitem, gray)
        text = pytesseract.image_to_string(Image.open(tempPathitem))
        return text

    def checkpogomainscreen(self, filename, hash):
        logger.debug("checkpogomainscreen: Checking close except nearby with: file {}, hash {}", filename, hash)
        mainscreen = 0
        try:
            screenshotRead = cv2.imread(filename)
        except Exception:
            logger.error("Screenshot corrupted :(")
            logger.debug("checkCloseExceptNearbyButton: Screenshot corrupted...")
            return False
        if screenshotRead is None:
            logger.error("checkCloseExceptNearbyButton: Screenshot corrupted :(")
            return False

        height, width, _ = screenshotRead.shape
        gray = screenshotRead[int(height) - int(round(height / 6)):int(height),
                              0: int(int(width) / 4)]
        height_, width_, _ = gray.shape
        radMin = int((width / float(6.8) - 3) / 2)
        radMax = int((width / float(6) + 3) / 2)
        gray = cv2.GaussianBlur(gray, (3, 3), 0)
        gray = cv2.Canny(gray, 100, 50, apertureSize=3)
        circles = cv2.HoughCircles(gray, cv2.HOUGH_GRADIENT, 1, width / 8, param1=100, param2=15, minRadius=radMin,
                                   maxRadius=radMax)
        if circles is not None:
            circles = np.round(circles[0, :]).astype("int")
            for (x, y, r) in circles:
                if x < width_ - width_/3:
                    mainscreen += 1

        if mainscreen > 0:
            logger.info("Found Avatar.")
            return True
        return False

    def checkCloseButton(self, filename, hash, communicator):
        logger.debug("checkCloseButton: Checking close with: file {}, hash {}", filename, hash)
        try:
            screenshotRead = cv2.imread(filename)
        except Exception:
            logger.error("Screenshot corrupted :(")
            logger.debug("checkCloseButton: Screenshot corrupted...")
            return False
        if screenshotRead is None:
            logger.error("checkCloseButton: Screenshot corrupted :(")
            return False

        if self.__readCircleCount(filename, hash,
                                  float(7.7), communicator, xcord=False, crop=True, click=True, canny=True) > 0:
            logger.debug("Found close button (X). Closing the window - Ratio: 10")
            return True

        if self.__checkClosePresent(filename, hash, 10, False):
            logger.debug("Found close button (X). Closing the window - Ratio: 10")
            return True
        if self.__checkClosePresent(filename, hash, 8, False):
            logger.debug("Found close button (X). Closing the window - Ratio: 8")
            return True
        elif self.__checkClosePresent(filename, hash, 12, False):
            logger.debug("Found close button (X). Closing the window - Ratio: 12")
            return True
        elif self.__checkClosePresent(filename, hash, 14, False):
            logger.debug("Found close button (X). Closing the window - Ratio: 14")
            return True
        elif self.__checkClosePresent(filename, hash, 13, False):
            logger.debug("Found close button (X). Closing the window - Ratio: 13")
            return True
        else:
            logger.debug("Could not find close button (X).")
            return False
