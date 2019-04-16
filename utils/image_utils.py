import cv2
from loguru import logger
from PIL import Image
from imagehash import dhash


def getImageHash(image, hashSize=8):
    try:
        image_temp = cv2.imread(image)
    except Exception as e:
        logger.error("Screenshot corrupted :(")
        logger.debug(e)
        return '0'
    if image_temp is None:
        logger.error("Screenshot corrupted :(")
        return '0'

    hashPic = Image.open(image)
    imageHash = dhash(hashPic, hashSize)
    return imageHash
