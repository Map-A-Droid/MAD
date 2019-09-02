import cv2
from imagehash import dhash
from PIL import Image
from utils.logging import logger


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

    with Image.open(image) as hashPic:
        imageHash = dhash(hashPic, hashSize)
        return imageHash
