import logging
import os

import cv2
import imutils
import numpy as np

log = logging.getLogger(__name__)


def mon_image_matching(args, url_img_name, fort_img_name, raidNo, hash):

    url_img = cv2.imread(url_img_name, 3)

    if (url_img is None):
        log.error('[Crop: ' + str(raidNo) + ' (' + str(hash) + ') ] ' +
                  'fort_image_matching: %s appears to be corrupted' % str(url_img_name))
        return 0.0

    fort_img = cv2.imread(fort_img_name, 3)

    if (fort_img is None):
        log.error('[Crop: ' + str(raidNo) + ' (' + str(hash) + ') ] ' +
                  'fort_image_matching: %s appears to be corrupted' % str(fort_img_name))
        return 0.0
    height, width, _ = url_img.shape
    height_f, width_f, _ = fort_img.shape

    fort_img = imutils.resize(fort_img, width=int(fort_img.shape[1] * 1))

    resized = imutils.resize(url_img, width=int(url_img.shape[1] * 1))
    crop = cv2.Canny(resized, 100, 200)

    if crop.mean() == 255 or crop.mean() == 0:
        return 0.0

    (tH, tW) = crop.shape[:2]

    fort_img = cv2.blur(fort_img, (3, 3))
    fort_img = cv2.Canny(fort_img, 50, 100)

    found = []
    for scale in np.linspace(args.npmFrom, args.npmValue, 10)[::-1]:

        resized = imutils.resize(
            fort_img, width=int(fort_img.shape[1] * scale))
        r = fort_img.shape[1] / float(resized.shape[1])

        if resized.shape[0] < tH or resized.shape[1] < tW:
            break

        result = cv2.matchTemplate(resized, crop, cv2.TM_CCOEFF_NORMED)
        (_, maxVal, _, maxLoc) = cv2.minMaxLoc(result)

        (endX, endY) = (int((maxLoc[0] + tW) * r), int((maxLoc[1] + tH) * r))

        if endY < height_f/2 or endX < width_f/2 or endY > height_f/2+height_f/2*0.4 or endY < height_f/2+height_f/2*0.3:
            maxVal = 0.0

        log.debug('[Crop: ' + str(raidNo) + ' (' + str(hash) + ') ] ' + 'Filename: ' +
                  str(url_img_name) + ' Matchvalue: ' + str(maxVal) + ' Scale: ' + str(scale))

        if not found or maxVal > found[0]:
            found = (maxVal, maxLoc, r)

    return found[0]


if __name__ == '__main__':
    fort_id = 'raid1'
    fort_img_path = os.getcwd() + '/' + str(fort_id) + '.jpg'
    url_img_path = os.getcwd() + 'ocr/mon_img/ic_raid_egg_rare.png'
    # log.debug(mon_image_matching('_mon_191_1.png','2_gym_51.9018472368_-0.521566117825_1535541942.24_False.jpg',False, 0.1, 1, 123))
