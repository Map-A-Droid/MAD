import cv2
from PIL import Image
from imagehash import dhash
from mapadroid.utils.logging import get_logger, LoggerEnums


logger = get_logger(LoggerEnums.utils)


def getImageHash(image, hashSize=8):
    try:
        image_temp = cv2.imread(image)
    except Exception:
        logger.error("Screenshot corrupted")
        return '0'
    if image_temp is None:
        logger.error("Screenshot corrupted")
        return '0'

    with Image.open(image) as hashPic:
        imageHash = dhash(hashPic, hashSize)
        return imageHash
