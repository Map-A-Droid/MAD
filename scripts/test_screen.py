import argparse
import math
import os
import sys

import cv2
import numpy as np
import pytesseract
from PIL import Image

from mapadroid.utils.resolution import Resocalculator

sys.path.append("..")


class testimage(object):
    def __init__(self, image, mode, xoffset=0, yoffset=0):

        self._image = cv2.imread(image)
        self._screen_y, self._screen_x, _ = self._image.shape
        self._mode = mode
        print(float(self._screen_y) / float(self._screen_x))

        self._resocalc = Resocalculator
        print(self._resocalc.get_x_y_ratio(
            self, self._screen_x, self._screen_y, xoffset, yoffset))

        print(self._resocalc.get_inventory_text_diff(self))

        if self._mode == "menu":
            self._image_check = self.check_menu(self._image)

        if self._mode == "open_close_menu":
            self._image_check = self.open_close_menu(self._image)

        if self._mode == "open_quest_menu":
            self._image_check = self.open_quest_menu(self._image)

        if self._mode == "open_del_item":
            self._image_check = self.open_del_item(self._image)

        if self._mode == "open_next_del_item":
            self._image_check = self.open_next_del_item(self._image)

        if self._mode == "get_click_item_minus":
            self._image_check = self.get_click_item_minus(self._image)

        if self._mode == "confirm_delete_item":
            self._image_check = self.confirm_delete_item(self._image)

        if self._mode == "open_del_quest":
            self._image_check = self.open_del_quest(self._image)

        if self._mode == "confirm_del_quest":
            self._image_check = self.confirm_del_quest(self._image)

        if self._mode == "open_gym":
            self._image_check = self.get_gym_click_coords(self._image)

        if self._mode == "check_button_big":
            self._image_check = self.look_for_button(self._image, 1.05, 2.20, upper=False)
            # 2.20, 3.01)

        if self._mode == "check_button_small":
            self._image_check = self.look_for_button(self._image, 2.20, 3.01, upper=True)

        if self._mode == "find_pokeball":
            self._image_check = self.find_pokeball(self._image)
            sys.exit(0)

        if self._mode == "check_mainscreen":
            self._image_check = self.check_mainscreen(self._image)
            sys.exit(0)

        if self._mode == "read_item_text":
            self._image_check = self.get_delete_item_text(self._image)

        cv2.namedWindow("output", cv2.WINDOW_KEEPRATIO)
        cv2.imshow("output", self._image_check)
        cv2.waitKey(0)

    def open_close_menu(self, image):
        print('Open Close Menu')
        x, y = self._resocalc.get_close_main_button_coords(self)[0], \
               self._resocalc.get_close_main_button_coords(self)[
                   1]
        return cv2.circle(image, (int(x), int(y)), 20, (0, 0, 255), -1)

    def check_menu(self, image):
        print('Check PokemonGo Menu')
        x, y = self._resocalc.get_item_menu_coords(
            self)[0], self._resocalc.get_item_menu_coords(self)[1]
        return cv2.circle(image, (int(x), int(y)), 20, (0, 0, 255), -1)

    def open_quest_menu(self, image):
        print('Open Quest Menu')
        x, y = self._resocalc.get_coords_quest_menu(
            self)[0], self._resocalc.get_coords_quest_menu(self)[1]
        return cv2.circle(image, (int(x), int(y)), 20, (0, 0, 255), -1)

    def open_del_item(self, image):
        print('Check Open del Item')

        x, y = self._resocalc.get_delete_item_coords(
            self)[0], self._resocalc.get_delete_item_coords(self)[1]
        return cv2.circle(image, (int(x), int(y)), 20, (0, 0, 255), -1)

    def open_next_del_item(self, image):
        print('Check Open next del Item')
        x, y = self._resocalc.get_delete_item_coords(
            self)[0], self._resocalc.get_delete_item_coords(self)[1]
        y += self._resocalc.get_next_item_coord(self)
        y += self._resocalc.get_next_item_coord(self)
        y += self._resocalc.get_next_item_coord(self)
        y += self._resocalc.get_next_item_coord(self)
        return cv2.circle(image, (int(x), int(y)), 20, (0, 0, 255), -1)

    def get_click_item_minus(self, image):
        print('Click minus item')
        x, y = self._resocalc.get_click_item_minus(self)
        return cv2.circle(image, (int(x), int(y)), 20, (0, 0, 255), -1)

    def confirm_delete_item(self, image):
        print('Check confirm delete item')
        x, y = self._resocalc.get_confirm_delete_item_coords(
            self)[0], self._resocalc.get_confirm_delete_item_coords(self)[1]
        return cv2.circle(image, (int(x), int(y)), 20, (0, 0, 255), -1)

    def open_del_quest(self, image):
        print('Check Open del quest')
        x, y = self._resocalc.get_delete_quest_coords(
            self)[0], self._resocalc.get_delete_quest_coords(self)[1]
        return cv2.circle(image, (int(x), int(y)), 20, (0, 0, 255), -1)

    def confirm_del_quest(self, image):
        print('Check confirm delete quest')
        x, y = self._resocalc.get_confirm_delete_quest_coords(
            self)[0], self._resocalc.get_confirm_delete_quest_coords(self)[1]
        return cv2.circle(image, (int(x), int(y)), 20, (0, 0, 255), -1)

    def get_gym_click_coords(self, image):
        print('Opening gym')
        x, y = self._resocalc.get_gym_click_coords(
            self)[0], self._resocalc.get_gym_click_coords(self)[1]
        print(x, y)
        return cv2.circle(image, (int(x), int(y)), 20, (0, 0, 255), -1)

    def find_pokeball(self, image):
        print('Check Pokeball Mainscreen')
        height, width, _ = image.shape
        image = image[int(height) - int(round(height / 4.5)):int(height),
                0: round(int(width) / 2)]
        output = image.copy()
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        radMin = int((width / float(7.5) - 3) / 2)
        radMax = int((width / float(6.5) + 3) / 2)
        gray = cv2.GaussianBlur(gray, (3, 3), 0)
        gray = cv2.Canny(gray, 100, 50, apertureSize=3)
        circles = cv2.HoughCircles(gray, cv2.HOUGH_GRADIENT, 1, width / 8,
                                   param1=100, param2=15, minRadius=radMin, maxRadius=radMax)
        if circles is not None:
            circles = np.round(circles[0, :]).astype("int")
            for (x, y, r) in circles:
                raidhash = output[y - r - 1:y + r + 1, x - r - 1:x + r + 1]
                cv2.imshow("output", np.hstack([raidhash]))
                cv2.waitKey(0)
        else:
            print('No Mainscreen found')

    def get_delete_item_text(self, image):
        print('Get item Text')
        x1, x2, y1, y2 = self._resocalc.get_delete_item_text(self)
        # y1 += self._resocalc.get_next_item_coord(self)
        # y2 += self._resocalc.get_next_item_coord(self)
        # y1 += self._resocalc.get_next_item_coord(self)
        # y2 += self._resocalc.get_next_item_coord(self)
        # y1 += self._resocalc.get_next_item_coord(self)
        # y2 += self._resocalc.get_next_item_coord(self)
        h = x1 - x2
        w = y1 - y2
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        gray = gray[int(y2):(int(y2) + int(w)), int(x2):(int(x2) + int(h))]
        cv2.imshow("output", gray)
        cv2.waitKey(0)
        filename = "{}.png".format(os.getpid())
        cv2.imwrite(filename, gray)
        with Image.open(filename) as im:
            text = pytesseract.image_to_string(im)
        os.remove(filename)
        print(text)
        return cv2.rectangle(image, (int(x1), int(y1)), (int(x2), int(y2)), (255, 0, 0), 2)

    def check_mainscreen(self, image):
        print('Check Mainscreen')
        mainscreen = 0

        height, width, _ = image.shape
        gray = image[int(height) - int(round(height / 6)):int(height),
               0: int(int(width) / 3)]
        original = gray
        height_, width_, _ = gray.shape
        radMin = int((width / float(6.8) - 3) / 2)
        radMax = int((width / float(6) + 3) / 2)
        gray = cv2.GaussianBlur(gray, (3, 3), 0)
        gray = cv2.Canny(gray, 100, 50, apertureSize=3)
        cv2.imshow("output", gray)
        cv2.waitKey(0)
        circles = cv2.HoughCircles(gray, cv2.HOUGH_GRADIENT, 1, width / 8, param1=100, param2=15,
                                   minRadius=radMin,
                                   maxRadius=radMax)
        if circles is not None:
            circles = np.round(circles[0, :]).astype("int")
            for (x, y, r) in circles:
                if x < width_ - width_ / 3:
                    cv2.circle(original, (x, y), r, (0, 255, 0), 4)
                    mainscreen += 1
                    raidhash = original[y - r - 1:y +
                                                  r + 1, x - r - 1:x + r + 1]
                    cv2.imshow("output", np.hstack([raidhash]))
                    cv2.waitKey(0)

        if mainscreen > 0:
            print("Found Avatar.")
            return True
        return False

    def look_for_button(self, filename, ratiomin, ratiomax, upper: bool = False):
        print("lookForButton: Reading lines")
        disToMiddleMin = None
        gray = cv2.cvtColor(filename, cv2.COLOR_BGR2GRAY)
        height, width, _ = filename.shape
        _widthold = float(width)
        print("lookForButton: Determined screenshot scale: " +
              str(height) + " x " + str(width))

        # resize for better line quality
        # gray = cv2.resize(gray, (0,0), fx=width*0.001, fy=width*0.001)
        height, width = gray.shape
        factor = width / _widthold

        gray = cv2.GaussianBlur(gray, (3, 3), 0)
        edges = cv2.Canny(gray, 50, 200, apertureSize=3)
        # checking for all possible button lines

        maxLineLength = (width / ratiomin) + (width * 0.18)
        print("lookForButton: MaxLineLength:" + str(maxLineLength))
        minLineLength = (width / ratiomax) - (width * 0.02)
        print("lookForButton: MinLineLength:" + str(minLineLength))

        kernel = np.ones((2, 2), np.uint8)
        # kernel = np.zeros(shape=(2, 2), dtype=np.uint8)
        edges = cv2.morphologyEx(edges, cv2.MORPH_GRADIENT, kernel)

        maxLineGap = 50
        lineCount = 0
        _x = 0
        _y = height
        lines = cv2.HoughLinesP(edges, rho=1, theta=math.pi / 180, threshold=90, minLineLength=minLineLength,
                                maxLineGap=5)
        if lines is None:
            return False

        lines = (self.check_lines(lines, height))

        _last_y = 0
        for line in lines:
            line = [line]
            for x1, y1, x2, y2 in line:
                if y1 == y2 and x2 - x1 <= maxLineLength and x2 - x1 >= minLineLength \
                        and y1 > height / 3 \
                        and (x2 - x1) / 2 + x1 < width / 2 + 50 and (x2 - x1) / 2 + x1 > width / 2 - 50:
                    lineCount += 1
                    disToMiddleMin_temp = y1 - (height / 2)
                    if upper:
                        if disToMiddleMin is None:
                            disToMiddleMin = disToMiddleMin_temp
                            click_y = y1 + 50
                            _last_y = y1
                            _x1 = x1
                            _x2 = x2
                        else:
                            if disToMiddleMin_temp < disToMiddleMin:
                                click_y = _last_y + ((y1 - _last_y) / 2)
                                _last_y = y1
                                _x1 = x1
                                _x2 = x2

                    else:
                        click_y = _last_y + ((y1 - _last_y) / 2)
                        _last_y = y1
                        _x1 = x1
                        _x2 = x2

                    print("lookForButton: Found Buttonline Nr. " + str(lineCount) + " - Line lenght: " + str(
                        x2 - x1) + "px Coords - X: " + str(x1) + " " + str(x2) + " Y: " + str(y1) + " " + str(
                        y2))

                    cv2.line(filename, (int(x1), int(y1)), (int(x2), int(y2)), (255, 0, 0), 5)

        if 1 < lineCount <= 6:
            click_x = int(((width - _x2) + ((_x2 - _x1) / 2)) /
                          round(factor, 2))
            click_y = int(click_y)
            print('lookForButton: found Button - click on it')
            return cv2.circle(filename, (int(click_x), int(click_y)), 20, (0, 0, 255), -1)

        elif lineCount > 6:
            print('lookForButton: found to much Buttons :) - close it')
            return cv2.circle(filename, (int(width - (width / 7.2)), int(height - (height / 12.19))),
                              20, (0, 0, 255), -1)

        print('lookForButton: did not found any Button')
        return False

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


ap = argparse.ArgumentParser()
ap.add_argument("-i", "--image", required=True, help="Path to the image")
ap.add_argument("-m", "--mode", required=True, help="Type of Image")
ap.add_argument("-xo", "--xoffset", required=False, help="X Offset")
ap.add_argument("-yo", "--yoffset", required=False, help="Y Offset")
args = vars(ap.parse_args())

xoffset = 0
if args["xoffset"]:
    xoffset = int(args["xoffset"])
yoffset = 0
if args["yoffset"]:
    yoffset = int(args["yoffset"])

test = testimage(args["image"], args["mode"], xoffset, yoffset)
