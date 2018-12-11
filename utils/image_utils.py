import logging

import cv2
from PIL import Image
from imagehash import dhash

log = logging.getLogger(__name__)


def getImageHash(image, hashSize=8):
    try:
        image_temp = cv2.imread(image)
    except Exception as e:
        log.error("Screenshot corrupted :(")
        log.debug(e)
        return '0'
    if image_temp is None:
        log.error("Screenshot corrupted :(")
        return '0'

    hashPic = Image.open(image)
    imageHash = dhash(hashPic, hashSize)
    return imageHash