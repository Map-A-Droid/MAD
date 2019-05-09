import os
import sys
import cv2
import imutils
import numpy as np
sys.path.append("..")
from utils.logging import logger
from utils.collections import Trash
from typing import List


def trash_image_matching(screen_img):
    clicklist: List[Trash] = []
    screen = cv2.imread(screen_img, 3)

    if screen is None:
        logger.error('trash_image_matching: {} appears to be corrupted', str(screen_img))
        return None

    trash = cv2.imread('utils/trashcan.png', 3)

    height, width, _ = screen.shape
    height_f, width_f, _ = trash.shape

    trash_crop = cv2.Canny(trash, 100, 200)

    if trash_crop.mean() == 255 or trash_crop.mean() == 0:
        return clicklist

    (tH, tW) = trash_crop.shape[:2]

    screen = cv2.blur(screen, (2, 2))
    screen = cv2.Canny(screen, 50, 100)

    for scale in np.linspace(0.1, 2, 10)[::-1]:

        resized = imutils.resize(
            trash_crop, width=int(trash_crop.shape[1] * scale))

        last_y_coord = 0
        res = cv2.matchTemplate(screen, resized, cv2.TM_CCOEFF_NORMED)
        threshold = 0.3
        loc = np.where(res >= threshold)
        boxcount = 0
        for pt in zip(*loc[::-1]):
            if pt[0] > width/4*3:
                x_coord = int(pt[0]  + tW / 2)
                y_coord = int(pt[1]  + tH / 2)
                # cv2.rectangle(screen, pt, (pt[0] + tW, pt[1] + tH), (255, 255, 255), 2)
                if last_y_coord > 0:
                    if last_y_coord + 100 > y_coord or last_y_coord - 100 > y_coord:
                        last_y_coord = y_coord
                    else:
                        clicklist.append(Trash(x_coord, y_coord))
                        last_y_coord = y_coord
                else:
                    clicklist.append(Trash(x_coord, y_coord))
                    last_y_coord = y_coord
                boxcount += 1

        #cv2.namedWindow("output", cv2.WINDOW_KEEPRATIO)
        #cv2.imshow("output", screen)
        #cv2.waitKey(0)

        if boxcount >= 1: break

    return clicklist


if __name__ == '__main__':
    fort_id = 'raid1'
    fort_img_path = os.getcwd() + '/' + str(fort_id) + '.jpg'
    url_img_path = os.getcwd() + 'ocr/mon_img/ic_raid_egg_rare.png'
    # print (trash_image_matching('screenshotredmi.png'))
