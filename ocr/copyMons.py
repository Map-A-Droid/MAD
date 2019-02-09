import glob
import json
import logging
import os
import os.path
from shutil import copyfile

import cv2
import numpy as np
from PIL import Image

log = logging.getLogger(__name__)


class MonRaidImages(object):

    @staticmethod
    def copyMons(pogoassets_path, db_wrapper):

        monList = []

        log.info('Processing Pokemon Matching....')
        with open('raidmons.json') as f:
            data = json.load(f)

        monImgPath = os.getcwd() + '/ocr/mon_img/'
        filePath = os.path.dirname(monImgPath)

        if not os.path.exists(filePath):
            log.info('ocr/mon_img directory created')
            os.makedirs(filePath)

        assetPath = pogoassets_path

        if not os.path.exists(assetPath):
            log.error('PogoAssets not found')
            exit(0)

        for file in glob.glob(monImgPath + "*mon*.png"):
            os.remove(file)

        for mons in data:
            for mon in mons['DexID']:
                lvl = mons['Level']
                if str(mon).find("_") > -1:
                    mon_split = str(mon).split("_")
                    mon = mon_split[0]
                    frmadd = mon_split[1]
                else:
                    frmadd = "00"

                mon = '{:03d}'.format(int(mon))
                monList.append(mon)

                monFile = monImgPath + '_mon_' + \
                    str(mon) + '_' + str(lvl) + '.png'

                if not os.path.isfile(monFile):

                    monFileAsset = assetPath + '/pokemon_icons/pokemon_icon_' + \
                        str(mon) + '_' + frmadd + '.png'

                    if not os.path.isfile(monFileAsset):
                        log.error('File ' + str(monFileAsset) + ' not found')
                        exit(0)

                    copyfile(monFileAsset, monFile)

                    image = Image.open(monFile)
                    image.convert("RGBA")
                    # Empty canvas colour (r,g,b,a)
                    canvas = Image.new('RGBA', image.size,
                                       (255, 255, 255, 255))
                    # Paste the image onto the canvas, using it's alpha channel as mask
                    canvas.paste(image, mask=image)
                    canvas.save(monFile, format="PNG")

                    monAsset = cv2.imread(monFile, 3)
                    height, width, channels = monAsset.shape
                    monAsset = cv2.inRange(monAsset, np.array(
                        [240, 240, 240]), np.array([255, 255, 255]))
                    cv2.imwrite(monFile, monAsset)
                    crop = cv2.imread(monFile, 3)
                    crop = crop[0:int(height), 0:int((width/10)*10)]
                    kernel = np.ones((2, 2), np.uint8)
                    crop = cv2.erode(crop, kernel, iterations=1)
                    kernel = np.ones((3, 3), np.uint8)
                    crop = cv2.morphologyEx(crop, cv2.MORPH_CLOSE, kernel)

                    #gray = cv2.cvtColor(crop,cv2.COLOR_BGR2GRAY)
                    #_,thresh = cv2.threshold(gray,1,255,cv2.THRESH_BINARY_INV)
                    #contours = cv2.findContours(thresh,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
                    #cnt = contours[0]
                    #x,y,w,h = cv2.boundingRect(cnt)
                    #crop = crop[y-1:y+h+1,x-1:x+w+1]
                    cv2.imwrite(monFile, crop)

        _monList = '|'.join(map(str, monList))
        dbWrapper = db_wrapper
        dbWrapper.clear_hash_gyms(_monList)

    @staticmethod
    def copyWeather(pogoasset):
        log.info('Processing Weather Pics')
        weatherImgPath = os.getcwd() + '/ocr/weather/'
        filePath = os.path.dirname(weatherImgPath)
        if not os.path.exists(filePath):
            log.info('weather directory created')
            os.makedirs(filePath)
        assetPath = pogoasset

        for file in glob.glob(os.path.join(assetPath, 'static_assets/png/weatherIcon_small_*.png')):

            MonRaidImages.read_transparent_png(file, os.path.join(
                'ocr/weather', os.path.basename(file)), 0)

    @staticmethod
    def read_transparent_png(assetFile, saveFile, bgcolor=255):
        image_4channel = cv2.imread(assetFile, cv2.IMREAD_UNCHANGED)
        alpha_channel = image_4channel[:, :, 3]
        rgb_channels = image_4channel[:, :, :3]

        white_background_image = np.ones_like(
            rgb_channels, dtype=np.uint8) * bgcolor

        alpha_factor = alpha_channel[:, :,
                                     np.newaxis].astype(np.float32) / 255.0
        alpha_factor = np.concatenate(
            (alpha_factor, alpha_factor, alpha_factor), axis=2)

        base = rgb_channels.astype(np.float32) * alpha_factor
        white = white_background_image.astype(np.float32) * (1 - alpha_factor)
        final_image = base + white

        cv2.imwrite(saveFile, final_image.astype(np.uint8))

        return assetFile

    @staticmethod
    def runAll(pogoassets_path, db_wrapper):
        MonRaidImages.copyMons(pogoassets_path, db_wrapper=db_wrapper)
        MonRaidImages.copyWeather(pogoassets_path)


if __name__ == '__main__':
    MonRaidImages.runAll('../../PogoAssets/', None)
