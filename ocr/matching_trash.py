import os
import sys
import cv2
import imutils
import numpy as np
sys.path.append("..")
from utils.logging import logger
from utils.collections import Trash
from typing import List


def get_delete_quest_coords(x):
    click_x = int(x) / 1.07
    return click_x


def get_delete_item_coords(x):
    click_x = int(x) / 1.09
    return click_x


def trash_image_matching(screen_img, full_screen):
    clicklist: List[Trash] = []
    screen = cv2.imread(screen_img)
    # print (screen.shape[:2])
    screen = cv2.cvtColor(screen, cv2.COLOR_BGR2GRAY)

    if screen is None:
        logger.error('trash_image_matching: {} appears to be corrupted', str(screen_img))
        return None

    trash = cv2.imread('utils/trashcan.png', 0)

    height, width = screen.shape
    _quest_x = get_delete_quest_coords(width)
    _inventory_x = get_delete_item_coords(width)

    if trash.mean() == 255 or trash.mean() == 0:
        return clicklist

    if width < 1080 and width > 720:
        sc_from = 0.5
        sc_till = 1
    elif width == 1080:
        sc_from = 0.5
        sc_till = 1.2
    elif width == 720:
        sc_from = 0.3
        sc_till = 0.9
    elif width == 1440:
        sc_from = 0.5
        sc_till = 1.5
    else:
        sc_from = 0.1
        sc_till = 2

    for scale in np.linspace(sc_from, sc_till, 15)[::-1]:

        resized = imutils.resize(
            trash, width=int(trash.shape[1] * scale))
        (tH, tW) = resized.shape[:2]

        last_y_coord = 0
        res = cv2.matchTemplate(screen, resized, cv2.TM_CCOEFF_NORMED)
        threshold = 0.5
        loc = np.where(res >= threshold)
        boxcount = 0
        for pt in zip(*loc[::-1]):
            screen_height_max = height/6*5
            if full_screen:
                screen_height_max = height
            if pt[0] > width/4*3 and pt[1] < screen_height_max:
                x_coord = int(pt[0] + tW / 2)
                y_coord = int(pt[1] + tH / 2)

                if last_y_coord > 0:
                    if last_y_coord + 100 > y_coord or last_y_coord - 100 > y_coord:
                        if (_inventory_x - 50 < x_coord < _inventory_x + 50) or \
                                (_quest_x - 50 < x_coord < _quest_x + 50):
                            last_y_coord = y_coord
                    else:
                        if (_inventory_x - 50 < x_coord < _inventory_x + 50) or \
                                (_quest_x - 50 < x_coord < _quest_x + 50):
                            clicklist.append(Trash(x_coord, y_coord))
                            last_y_coord = y_coord
                            # cv2.rectangle(screen, pt, (pt[0] + tW, pt[1] + tH), (128, 128, 128), 2)
                else:
                    if (_inventory_x - 50 < x_coord < _inventory_x + 50) or \
                            (_quest_x - 50 < x_coord < _quest_x + 50):
                        clicklist.append(Trash(x_coord, y_coord))
                        last_y_coord = y_coord
                        # cv2.rectangle(screen, pt, (pt[0] + tW, pt[1] + tH), (128, 128, 128), 2)
                boxcount += 1

        # cv2.namedWindow("output", cv2.WINDOW_KEEPRATIO)
        # cv2.imshow("output", screen)
        # cv2.waitKey(0)

        if boxcount >= 1: break

    return clicklist


if __name__ == '__main__':
    fort_id = 'raid1'
    fort_img_path = os.getcwd() + '/' + str(fort_id) + '.jpg'
    url_img_path = os.getcwd() + 'ocr/mon_img/ic_raid_egg_rare.png'
    # print (trash_image_matching('xxxxxxxx.jpg'))
