import argparse
import sys

import cv2
import numpy as np
from utils.resolution import Resocalculator

sys.path.append("..")


class testimage(object):
    def __init__(self, image, mode):

        self._image = cv2.imread(image)
        self._screen_y, self._screen_x, _ = self._image.shape
        self._mode = mode
        print(float(self._screen_y) / float(self._screen_x))

        self._resocalc = Resocalculator
        print(self._resocalc.get_x_y_ratio(
            self, self._screen_x, self._screen_y))

        if self._mode == "menu":
            self._image_check = self.check_menu(self._image)

        if self._mode == "open_del_item":
            self._image_check = self.open_del_item(self._image)

        if self._mode == "open_next_del_item":
            self._image_check = self.open_next_del_item(self._image)

        if self._mode == "swipe_del_item":
            self._image_check = self.swipe_del_item(self._image)

        if self._mode == "confirm_delete_item":
            self._image_check = self.confirm_delete_item(self._image)

        if self._mode == "open_del_quest":
            self._image_check = self.open_del_quest(self._image)

        if self._mode == "confirm_del_quest":
            self._image_check = self.confirm_del_quest(self._image)

        if self._mode == "open_gym":
            self._image_check = self.get_gym_click_coords(self._image)

        if self._mode == "find_pokeball":
            self._image_check = self.find_pokeball(self._image)
            sys.exit(0)

        cv2.imshow("output", self._image_check)
        cv2.waitKey(0)

    def check_menu(self, image):
        print('Check PokemonGo Menu')
        x, y = self._resocalc.get_item_menu_coords(
            self)[0], self._resocalc.get_item_menu_coords(self)[1]
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
        return cv2.circle(image, (int(x), int(y)), 20, (0, 0, 255), -1)

    def swipe_del_item(self, image):
        print('Swipe del item')
        x1, x2, y = self._resocalc.get_swipe_item_amount(self)[0], self._resocalc.get_swipe_item_amount(self)[
            1], self._resocalc.get_swipe_item_amount(self)[2]
        return cv2.line(image, (int(x1), int(y)), (int(x2), int(y)), (255, 0, 0), 5)

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
        return cv2.circle(image, (int(x), int(y)), 20, (0, 0, 255), -1)

    def find_pokeball(self, image):
        print('Check Pokeball Mainscreen')
        height, width, _ = image.shape
        image = image[int(height) - int(round(height / 4.5)):int(height),
                      round(int(width) / 2) - round(int(width) / 8):round(int(width) / 2) + round(
            int(width) / 8)]
        output = image.copy()
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        radMin = int((width / float(8.5) - 3) / 2)
        radMax = int((width / float(7.5) + 3) / 2)
        gray = cv2.GaussianBlur(gray, (3, 3), 0)
        gray = cv2.Canny(gray, 100, 50, apertureSize=3)
        circles = cv2.HoughCircles(gray, cv2.HOUGH_GRADIENT, 1, width / 8,
                                   param1=100, param2=15, minRadius=radMin, maxRadius=radMax)
        if circles is not None:
            circles = np.round(circles[0, :]).astype("int")
            for (x, y, r) in circles:
                raidhash = output[y-r-1:y+r+1, x-r-1:x+r+1]
                cv2.imshow("output", np.hstack([raidhash]))
                cv2.waitKey(0)
        else:
            print('No Mainscreen found')


ap = argparse.ArgumentParser()
ap.add_argument("-i", "--image", required=True, help="Path to the image")
ap.add_argument("-m", "--mode", required=True, help="Type of Image")
args = vars(ap.parse_args())


test = testimage(args["image"], args["mode"])
