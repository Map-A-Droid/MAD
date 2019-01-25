# -*- coding: utf-8 -*-
import datetime
import glob
import json
import logging
import os
import re
import time
from shutil import copyfile

import cv2
import imagehash
import numpy as np
import pytesseract
from PIL import Image

from .matching import fort_image_matching
from .matching_mon import mon_image_matching

log = logging.getLogger(__name__)

# egg IDs are always the same, just remember to decrement your raidlevel
eggIdsByLevel = [1, 1, 2, 2, 3]


class Scanner:
    def __init__(self, args, db_wrapper, hash):
        self.args = args
        self.uniqueHash = hash
        # new www service
        self.www_hash = 'ocr/www_hash'
        self.tempPath = args.temp_path
        self.unknownPath = args.unknown_path

        self.db_wrapper = db_wrapper

        if not os.path.exists(self.tempPath):
            log.info('Temp directory created')
            os.makedirs(self.tempPath)

        if not os.path.exists(self.unknownPath):
            log.info('Unknow directory created')
            os.makedirs(self.unknownPath)

        if not os.path.exists(self.www_hash):
            log.info('www_hash directory created')
            os.makedirs(self.www_hash)

    def detectRaidTime(self, raidpic, hash, raidNo, radius):
        zero = datetime.datetime.now()
        unixnow = time.mktime(zero.timetuple())
        log.debug('[Crop: ' + str(raidNo) + ' (' + str(self.uniqueHash) +
                  ') ] ' + 'detectRaidTime: Reading Raidtimer')
        height, width, channel = raidpic.shape
        raidtimer = raidpic[int(round(radius*2*0.03)+(2*radius)+(radius*2*0.265)):int(
            round(radius*2*0.03)+(2*radius)+(radius*2*0.43)), 0:width]
        raidtimer = cv2.resize(raidtimer, (0, 0), fx=2,
                               fy=2, interpolation=cv2.INTER_CUBIC)
        emptyRaidTempPath = os.path.join(
            self.tempPath, str(raidNo) + str(hash) + '_emptyraid.png')
        cv2.imwrite(emptyRaidTempPath, raidtimer)
        rt = Image.open(emptyRaidTempPath)
        gray = rt.convert('L')
        bw = gray.point(lambda x: 0 if x < 200 else 255, '1')
        raidtimer = pytesseract.image_to_string(bw, config='--psm 6 --oem 3').replace(' ', '').replace('~', '')\
            .replace('o', '0').replace('O', '0').replace('"', '').replace('-', '').replace('.', ':')\
            .replace('B', '8').replace('—', '').replace('_', '').replace("'", "").replace('U', '0').replace('/', '7')
        log.debug('[Crop: ' + str(raidNo) + ' (' + str(self.uniqueHash) + ') ] '
                  + 'detectRaidTime: detect raidtimer text: %s' % raidtimer)
        # cleanup
        os.remove(emptyRaidTempPath)
        raidFound = len(raidtimer) > 0
        if raidFound:
            if ':' in raidtimer:
                log.info('[Crop: ' + str(raidNo) + ' (' + str(self.uniqueHash) + ') ] '
                         + 'detectRaidTime: found raidtimer %s' % raidtimer)
                hatchTime = self.getHatchTime(raidtimer, raidNo)

                if hatchTime:
                    log.info('[Crop: ' + str(raidNo) + ' (' + str(self.uniqueHash) +
                             ') ] ' + 'detectRaidTime: Hatchtime %s' % str(hatchTime))
                    # if hatchTime > unixnow + (int(args.raid_time) * 60) or hatchTime < unixnow:
                    # log.info('[Crop: ' + str(raidNo) + ' (' + str(self.uniqueHash) +') ] ' + 'detectRaidTime: Hatchtime not logical')
                    # return (raidFound, False, False, False)
                    # raidstart = getHatchTime(self, raidtimer) - self.timezone * (self.timezone*60*60)
                    raidstart = hatchTime  # - (self.timezone * 60 * 60)
                    # - (self.timezone * 60 * 60)
                    raidend = hatchTime + (int(self.args.raid_time) * 60)
                    #raidend = getHatchTime(self, raidtimer) + int(45*60) - (self.timezone*60*60)
                    log.debug('[Crop: ' + str(raidNo) + ' (' + str(self.uniqueHash) + ') ] ' +
                              'detectRaidTime: Start: ' + str(raidstart) + ' End: ' + str(raidend))
                    return (raidFound, True, raidstart, raidend)
                else:
                    log.info('[Crop: ' + str(raidNo) + ' (' + str(self.uniqueHash) +
                             ') ] ' + 'detectRaidTime: Could not read Raidtime')
                    return (raidFound, True, False, False)

            else:
                log.info('[Crop: ' + str(raidNo) + ' (' + str(self.uniqueHash) + ') ] ' +
                         'detectRaidTime: No correct format for Raidtime found')
                return (raidFound, False, '0', '0')
        else:
            log.info('[Crop: ' + str(raidNo) + ' (' + str(self.uniqueHash) +
                     ') ] ' + 'detectRaidTime: No RaidTime found')
            return (raidFound, False, False, False)

    def detectRaidEndtimer(self, raidpic, hash, raidNo, radius):
        zero = datetime.datetime.now()
        unixnow = time.mktime(zero.timetuple())
        log.debug('[Crop: ' + str(raidNo) + ' (' + str(self.uniqueHash) +
                  ') ] ' + 'detectRaidEndtimer: Reading Raidtimer')
        height, width, channel = raidpic.shape
        raidtimer = raidpic[int(round(radius*2*0.03)+(2*radius)+(radius*2*0.10))                            :int(round(radius*2*0.03)+(2*radius)+(radius*2*0.23)), 0:width]
        raidtimer = cv2.resize(raidtimer, (0, 0), fx=3,
                               fy=3, interpolation=cv2.INTER_CUBIC)
        emptyRaidTempPath = os.path.join(
            self.tempPath, str(raidNo) + str(hash) + '_endraid.png')
        cv2.imwrite(emptyRaidTempPath, raidtimer)
        rt = Image.open(emptyRaidTempPath)
        gray = rt.convert('L')
        bw = gray.point(lambda x: 0 if x < 200 else 255, '1')

        raidtimer = pytesseract.image_to_string(bw, config='--psm 6 --oem 3').replace(' ', '').replace('~', '').replace('o', '0').replace('O', '0').replace('"', '').replace(
            '-', '').replace('.', ':').replace('B', '8').replace('A', '4').replace('—', '').replace('_', '').replace("'", "").replace('U', '0').replace('/', '7')
        log.debug('[Crop: ' + str(raidNo) + ' (' + str(self.uniqueHash) + ') ] ' +
                  'detectRaidEndtimer: detect raidendtimer text: ' + str(raidtimer))

        os.remove(emptyRaidTempPath)
        raidEndFound = len(raidtimer) > 0

        if raidEndFound:
            if ':' in raidtimer:
                now = datetime.datetime.now()
                log.info('[Crop: ' + str(raidNo) + ' (' + str(self.uniqueHash) + ') ] ' +
                         'detectRaidEndtimer: found raidendtimer %s' % raidtimer)
                endTime = self.getEndTime(raidtimer, raidNo)
                if endTime:
                    log.info('[Crop: ' + str(raidNo) + ' (' + str(self.uniqueHash) +
                             ') ] ' + 'detectRaidEndtimer: Endtime %s' % str(endTime))
                    if endTime > unixnow + (int(self.args.raid_time) * 60):
                        log.info('[Crop: ' + str(raidNo) + ' (' + str(self.uniqueHash) +
                                 ') ] ' + 'detectRaidEndtimer: Endtime not logical')
                        return (raidEndFound, False, False)
                    #raidstart = getHatchTime(self, raidtimer) - self.timezone * (self.timezone*60*60)
                    raidend = endTime  # - (self.timezone * 60 * 60)
                    #raidend = getHatchTime(self, raidtimer) + int(45*60) - (self.timezone*60*60)
                    log.info('[Crop: ' + str(raidNo) + ' (' + str(self.uniqueHash) +
                             ') ] ' + 'detectRaidEndtimer: End: %s' % str(raidend))
                    return (raidEndFound, True, raidend)
                else:
                    log.info('[Crop: ' + str(raidNo) + ' (' + str(self.uniqueHash) +
                             ') ] ' + 'detectRaidEndtimer: Could not read ReadEndTime')
                    return (raidEndFound, False, False)

            else:
                log.info('[Crop: ' + str(raidNo) + ' (' + str(self.uniqueHash) + ') ] ' +
                         'detectRaidEndtimer: No correct format for Raidendtime found')
                return (raidEndFound, False, '0')
        else:
            log.info('[Crop: ' + str(raidNo) + ' (' + str(self.uniqueHash) +
                     ') ] ' + 'detectRaidEndtimer: No RaidEndTime found')
            return (raidEndFound, False, False)

    def detectRaidBoss(self, raidpic, lvl, hash, raidNo):
        foundmon = None
        monID = None
        log.info('[Crop: ' + str(raidNo) +
                 ' (' + str(self.uniqueHash) + ') ] ' + 'Extracting Raidboss')
        picName = os.path.join(self.tempPath, str(
            hash) + '_raidboss' + str(raidNo) + '.jpg')
        # self.genCannyMonPic(raidpic, picName)
        cv2.imwrite(picName, raidpic)

        log.debug('[Crop: ' + str(raidNo) + ' (' + str(self.uniqueHash) +
                  ') ] ' + 'detectRaidBoss: Scanning Raidboss')
        monHash = None
        log.debug('[Crop: ' + str(raidNo) + ' (' + str(self.uniqueHash) +
                  ') ] ' + 'detectRaidBoss: Monhash: ' + str(monHash))

        if monHash is None:
            for file in glob.glob("ocr/mon_img/_mon_*_" + str(lvl) + ".png"):
                log.debug("Comparing to %s" % str(file))
                find_mon = mon_image_matching(
                    self.args, file, picName, raidNo, hash)

                if foundmon is None or find_mon > foundmon[0]:
                    foundmon = find_mon, file

                if foundmon and foundmon[0] > 0.01:
                    monSplit = foundmon[1].split('_')
                    monID = monSplit[3]

            # we found the mon that's most likely to be the one that's in the crop
            log.info('[Crop: ' + str(raidNo) + ' (' + str(self.uniqueHash) +
                     ') ] ' + 'detectRaidBoss: Found mon in mon_img: ' + str(monID))

        else:
            os.remove(picName)
            return monHash, picName

        if monID:
            #self.imageHash(picName, monID, False, 'mon-' + str(lvl), raidNo)
            os.remove(picName)
            return monID, picName

        log.debug('[Crop: ' + str(raidNo) +
                  ' (' + str(self.uniqueHash) + ') ] ' + 'No Mon found!')

        os.remove(picName)
        return False, picName

    def detectLevel(self, raidpic, hash, raidNo, radius):
        foundlvl = None
        lvl = None

        log.info('[Crop: ' + str(raidNo) +
                 ' (' + str(self.uniqueHash) + ') ] ' + 'Scanning Level')
        height, width, channel = raidpic.shape
        raidlevel = raidpic[int(round(radius*2*0.03)+(2*radius)+(radius*2*0.43))                            :int(round(radius*2*0.03)+(2*radius)+(radius*2*0.68)), 0:width]
        raidlevel = cv2.resize(raidlevel, (0, 0), fx=0.5, fy=0.5)

        imgray = cv2.cvtColor(raidlevel, cv2.COLOR_BGR2GRAY)
        imgray = cv2.GaussianBlur(imgray, (9, 9), 2)
        #kernel = np.ones((5,5),np.uint8)
        #imgray = cv2.morphologyEx(imgray, cv2.MORPH_CLOSE, kernel)
        ret, thresh = cv2.threshold(imgray, 220, 255, 0)
        (_, contours, _) = cv2.findContours(
            thresh, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

        lvl = len(contours)-1

        if lvl >= 1 and lvl <= 5:

            log.info('[Crop: ' + str(raidNo) + ' (' + str(self.uniqueHash) +
                     ') ] ' + 'detectLevel: found level %s' % str(lvl))
            return lvl

        log.info('[Crop: ' + str(raidNo) + ' (' + str(self.uniqueHash) +
                 ') ] ' + 'detectLevel: could not find level')
        return None

    def checkDummy(self, raidpic, x1, x2, y1, y2, hash, raidNo, radius):
        foundgym = None
        log.debug('[Crop: ' + str(raidNo) + ' (' + str(self.uniqueHash) +
                  ') ] ' + 'checkDummy: Check for dummy Gym Image')

        template = ("ocr/mon_img/dummy_nearby.jpg")

        find_gym = fort_image_matching(
            raidpic, template, True, 0.9, raidNo, hash, True, radius, x1, x2, y1, y2)

        if find_gym >= 0.9:
            return True
        return False

    def detectGym(self, raidpic, hash, raidNo, captureLat, captureLng, radius, monId=None):
        foundgym = None
        gymId = None
        x1 = 0.30
        x2 = 0.62
        y1 = 0.62
        y2 = 1.23

        foundMonCrops = False

        log.info('[Crop: ' + str(raidNo) + ' (' +
                 str(self.uniqueHash) + ') ] ' + 'detectGym: Scanning Gym')

        # if gymHash is none, we haven't seen the gym yet, otherwise, gymHash == gymId we are looking for
        if monId:
            log.debug('[Crop: ' + str(raidNo) + ' (' + str(self.uniqueHash) +
                      ') ] ' + 'detectGym: Got Mon-ID for Gym-Detection %s' % monId)
            with open('monsspec.json') as f:
                data = json.load(f)

            if str(monId) in data:
                foundMonCrops = True
                crop = data[str(monId)]["Crop"]
                log.debug('[Crop: ' + str(raidNo) + ' (' + str(self.uniqueHash) +
                          ') ] ' + 'detectGym: Found other Crops for Mon %s' % monId)
                log.debug(str(crop))
                x1 = crop['X1']
                x2 = crop['X2']
                y1 = crop['Y1']
                y2 = crop['Y2']

        log.debug('[Crop: ' + str(raidNo) + ' (' + str(self.uniqueHash) + ') ] ' +
                  'detectGym: Cropsizes: x1:%s, x2:%s, y1:%s, y2:%s' % (str(x1), str(x2), str(y1), str(y2)))

        gymHashvalue = self.getImageHash(
            raidpic, True, raidNo, 'gym', x1, x2, y1, y2, radius)
        gymHash = self.imageHashExists(
            raidpic, True, 'gym', raidNo, x1, x2, y1, y2, radius)

        if gymHash is None:

            if self.checkDummy(raidpic, x1, x2, y1, y2, hash, raidNo, radius):
                log.info('[Crop: ' + str(raidNo) + ' (' + str(self.uniqueHash) +
                         ') ] ' + 'detectGym: Found dummy gym pic')
                self.unknownfound(raidpic, 'unkgym', False, raidNo,
                                  hash, False, gymHashvalue, captureLat, captureLng)
                return 'dummy'

            log.debug('[Crop: ' + str(raidNo) + ' (' + str(self.uniqueHash) +
                      ') ] ' + 'detectGym: No Gym-Hash: found - searching')
            log.debug('[Crop: ' + str(raidNo) + ' (' + str(self.uniqueHash) +
                      ') ] ' + 'detectGym: Searching closest gyms')
            if captureLat == '9999':
                distance = 99
            else:
                distance = str(self.args.gym_scan_distance)

            closestGymIds = self.db_wrapper.get_near_gyms(captureLat, captureLng, hash, raidNo, distance,
                                                          unique_hash=self.uniqueHash)

            log.debug('[Crop: ' + str(raidNo) + ' (' +
                      str(self.uniqueHash) + ') ] ' + 'detectGym: Detecting Gym')
            for closegym in closestGymIds:
                candidates = glob.glob(
                    "ocr/gym_img/_" + str(closegym[0]) + "_.jpg")
                for file in candidates:
                    find_gym = fort_image_matching(raidpic, file, True, float(
                        self.args.gym_detection_value), raidNo, hash, checkX=True, radius=radius, x1=x1, x2=x2, y1=y1, y2=y2)
                    log.debug('[Crop: ' + str(raidNo) + ' (' + str(self.uniqueHash) + ') ] ' +
                              'detectGym: Compare Gym-ID - ' + str(closegym[0]) + ' - Match: ' + str(find_gym))
                    if foundgym is None or find_gym > foundgym[0]:
                        foundgym = find_gym, file

                    if foundgym and foundgym[0] >= float(self.args.gym_detection_value):
                        # okay, we very likely found our gym
                        gymSplit = foundgym[1].split('_')
                        gymId = gymSplit[2]

        else:
            self.imageHash(raidpic, gymHash, True, 'gym',
                           raidNo, x1, x2, y1, y2, radius)
            log.info('[Crop: ' + str(raidNo) + ' (' + str(self.uniqueHash) +
                     ') ] ' + 'detectGym: Detected Gym-ID: ' + str(gymHash))
            return gymHash

        if gymId:
            log.info('[Crop: ' + str(raidNo) + ' (' + str(self.uniqueHash) +
                     ') ] ' + 'detectGym: Detected Gym - Gym-ID: ' + str(gymId))
            gymHash = self.imageHash(
                raidpic, gymId, True, 'gym', raidNo, x1=x1, x2=x2, y1=y1, y2=y2, radius=radius)
            self.unknownfound(raidpic, 'gym', False, raidNo,
                              hash, False, gymHashvalue, '0', '0')
            return gymId
        else:
            # we could not find the gym...
            self.unknownfound(raidpic, 'unkgym', False, raidNo,
                              hash, False, gymHashvalue, captureLat, captureLng)
            return None

    def unknownfound(self, raidpic, type, zoom, raidNo, hash, captureTime, imageHash=0, lat=0, lng=0):

        if captureTime:
            text = datetime.datetime.fromtimestamp(float(captureTime))
            text = "Scanned: " + str(text.strftime("%Y-%m-%d %H:%M"))
            self.addTextToCrop(raidpic, text, True)

        raidpic = cv2.imread(raidpic)
        if imageHash:
            existFile = os.path.join(self.www_hash, str(
                type) + "_*_" + str(imageHash) + ".jpg")
            if not glob.glob(existFile):
                cv2.imwrite(os.path.join(self.www_hash, str(
                    type) + "_" + str(lat) + "_" + str(lng) + "_" + str(imageHash) + ".jpg"), raidpic)
                log.debug('[Crop: ' + str(raidNo) + ' (' + str(self.uniqueHash) + ') ] ' + 'saveforweb: Write hash file for www: ' +
                          str(type) + "_" + str(lat) + "_" + str(lng) + "_" + str(imageHash) + ".jpg")
            else:
                log.debug('[Crop: ' + str(raidNo) + ' (' + str(self.uniqueHash) + ') ] ' + 'saveforweb: Hash file for www already exists: ' +
                          str(type) + "_" + str(lat) + "_" + str(lng) + "_" + str(imageHash) + ".jpg")
        else:
            cv2.imwrite(os.path.join(self.unknownPath, str(raidNo) + "_" + str(type) + "_" + str(
                lat) + "_" + str(lng) + "_" + str(time.time()) + "_" + str(imageHash) + ".jpg"), raidpic)
            log.debug('[Crop: ' + str(raidNo) + ' (' + str(self.uniqueHash) + ') ] ' + 'unknownfound: Write unknown file: ' +
                      str(type) + "_" + str(lat) + "_" + str(lng) + "_" + str(time.time()) + ".jpg")
        return True

    def addTextToCrop(self, picture, text, grayscale=False):
        from PIL import Image, ImageFont, ImageDraw
        img = Image.open(picture)
        draw = ImageDraw.Draw(img)
        font = ImageFont.truetype('font/arial.ttf', 10)
        x, y = 0, 0

        w, h = font.getsize(text)
        draw.rectangle((x, y, x + img.size[0], y + h + 1), fill='black')
        if grayscale:
            draw.text((x, y), text, (255), font=font)
        else:
            draw.text((x, y), text, (255, 255, 255), font=font)
        img.save(picture)

    def decodeHashJson(self, hashJson, raidNo):
        data = json.loads(hashJson)
        log.debug('[Crop: ' + str(raidNo) + ' (' +
                  str(self.uniqueHash) + ') ] ' + 'Decoding Raid Hash Json')

        raidGym = data['gym']
        raidLvl = data["lvl"]
        raidMon = data["mon"]

        return raidGym, raidLvl, raidMon

    def encodeHashJson(self, gym, lvl, mon, raidNo):
        log.debug('[Crop: ' + str(raidNo) + ' (' +
                  str(self.uniqueHash) + ') ] ' + 'Encoding Raid Hash Json')
        hashJson = json.dumps(
            {'gym': gym, 'lvl': lvl, 'mon': mon, 'lvl': lvl}, separators=(',', ':'))
        return hashJson

    def cropImage(self, image, raidNo, radius):
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (7, 7), 2)
        output = image.copy()
        height, width, channel = output.shape
        output = output[0:round(height*2/3), 0:width]
        image_cols, image_rows, _ = image.shape
        circles = cv2.HoughCircles(gray, cv2.HOUGH_GRADIENT, 1, 20,
                                   param1=50, param2=30, minRadius=radius, maxRadius=radius)
        if circles is not None:
            circles = np.round(circles[0, :]).astype("int")
            for (x, y, r) in circles:
                log.debug('[Crop: ' + str(raidNo) + ' (' + str(self.uniqueHash) + ') ] ' +
                          'cropImage: Detect crop coordinates x: ' + str(x) + ' y: ' + str(y) + ' with radius: ' + str(r))
                new_crop = output[y-r:y+r, x-r:x+r]
                return new_crop
        return False

    def start_detect(self, filenameOfCrop, hash, raidNo, captureTime, captureLat, captureLng, orgFileName, radius):
        log.debug('[Crop: ' + str(raidNo) + ' (' + str(self.uniqueHash) +
                  ') ] ' + 'start_detect: Starting detection of crop')
        log.debug('[Crop: ' + str(raidNo) + ' (' + str(self.uniqueHash) + ') ] ' +
                  'start_detect: Original Filename: ' + str(orgFileName))
        log.debug('[Crop: ' + str(raidNo) + ' (' + str(self.uniqueHash) +
                  ') ] ' + 'start_detect: Original Lat: ' + str(captureLat))
        log.debug('[Crop: ' + str(raidNo) + ' (' + str(self.uniqueHash) +
                  ') ] ' + 'start_detect: Original Lng: ' + str(captureLng))
        log.debug('[Crop: ' + str(raidNo) + ' (' + str(self.uniqueHash) +
                  ') ] ' + 'start_detect: Capture Time: ' + str(captureTime))
        if not os.path.isfile(filenameOfCrop):
            log.error('[Crop: ' + str(raidNo) + ' (' + str(self.uniqueHash) + ') ] ' +
                      'start_detect: File does not exist: %s' % str(filenameOfCrop))
            return

        monfound = False
        eggfound = False

        log.debug('[Crop: ' + str(raidNo) + ' (' + str(self.uniqueHash) + ') ] ' +
                  'start_detect: Starting analysis of ID %s' % str(hash))

        img = cv2.imread(filenameOfCrop, 3)

        raidhash = self.cropImage(img, raidNo, radius)

        raidhashPic = os.path.join(self.tempPath, str(
            hash) + "_raidhash" + str(raidNo) + ".jpg")
        cv2.imwrite(raidhashPic, raidhash)

        log.debug('[Crop: ' + str(raidNo) + ' (' + str(self.uniqueHash) +
                  ') ] ' + 'start_detect: Generating Raidhash')
        genRaidHash = self.getImageHash(raidhashPic, False, raidNo, 'raid')

        # get (raidstart, raidend, raidtimer) as (timestamp, timestamp, human-readable hatch)
        raidtimer = self.detectRaidTime(img, hash, raidNo, radius)
        log.debug('[Crop: ' + str(raidNo) + ' (' + str(self.uniqueHash) +
                  ') ] ' + 'start_detect: Got raidtime %s' % (str(raidtimer)))

        # first item in tuple stands for raid present in crop or not
        if (not raidtimer[0]):
            # there is no raid, stop analysis of crop, abandon ship
            os.remove(filenameOfCrop)
            os.remove(raidhashPic)
            log.debug('[Crop: ' + str(raidNo) + ' (' + str(self.uniqueHash) + ') ] ' +
                      'start_detect: Crop does not show a raid, stopping analysis')
            return False

        # second item is true for egg present, False for mon present
        eggfound = raidtimer[1]
        # will be 0 if eggfound = False. We report a mon anyway
        raidstart = raidtimer[2]
        # will be 0 if eggfound = False. We report a mon anyway
        raidend = raidtimer[3]

        if (not raidstart or not raidend):
            # there is no raid, stop analysis of crop, abandon ship
            os.remove(filenameOfCrop)
            os.remove(raidhashPic)
            log.debug('[Crop: ' + str(raidNo) + ' (' + str(self.uniqueHash) + ') ] ' +
                      'start_detect: Crop does not show a valid time, stopping analysis')
            return False

        log.debug('[Crop: ' + str(raidNo) + ' (' + str(self.uniqueHash) +
                  ') ] ' + 'start_detect: Creating Hash overall')
        raidHash = self.imageHashExists(raidhashPic, False, 'raid', raidNo)
        log.debug('[Crop: ' + str(raidNo) + ' (' + str(self.uniqueHash) +
                  ') ] ' + 'start_detect: detectRaidHash: ' + str(raidHash))

        # we need the raid level to make the possible set of mons smaller
        raidlevel = self.detectLevel(img, hash, raidNo, radius)
        log.debug('[Crop: ' + str(raidNo) + ' (' + str(self.uniqueHash) + ') ] ' +
                  'start_detect: Determined raidlevel to be %s' % (str(raidlevel)))

        if raidHash:
            raidHash_ = self.decodeHashJson(raidHash, raidNo)
            gym = raidHash_[0]
            lvl = raidHash_[1]
            mon = raidHash_[2]

            if lvl == raidlevel and raidlevel is not None:

                if not mon:
                    lvl = self.detectLevel(
                        img, hash, raidNo, radius)  # redetect level
                    log.debug('[Crop: ' + str(raidNo) + ' (' + str(self.uniqueHash) + ') ] ' +
                              'start_detect: Determined raidlevel to be %s' % (str(lvl)))

                    if lvl is None:
                        log.error('[Crop: ' + str(raidNo) + ' (' + str(self.uniqueHash) + ') ] ' +
                                  'start_detect: Could not determine raidlevel. Filename of Crop: %s' % (filenameOfCrop))
                        os.remove(filenameOfCrop)
                        os.remove(raidhashPic)
                        return True

                    log.debug('[Crop: ' + str(raidNo) + ' (' + str(self.uniqueHash) + ') ] ' +
                              'start_detect: Found Raidhash with an egg - fast submit')
                    log.debug('[Crop: ' + str(raidNo) + ' (' + str(self.uniqueHash) + ') ] ' +
                              'start_detect: Found egg level %s starting at %s and ending at %s. GymID: %s' % (lvl, raidstart, raidend, gym))
                    self.db_wrapper.submit_raid(str(gym), None, lvl, raidstart, raidend, 'EGG', raidNo, captureTime,
                                                unique_hash=self.uniqueHash)
                else:

                    raidend = self.detectRaidEndtimer(
                        img, hash, raidNo, radius)
                    if raidend[1]:
                        log.debug('[Crop: ' + str(raidNo) + ' (' + str(self.uniqueHash) + ') ] ' +
                                  'start_detect: Found Raidhash with an mon and endtime - fast submit')
                        log.debug('[Crop: ' + str(raidNo) + ' (' + str(self.uniqueHash) + ') ] ' +
                                  'start_detect: Submitting mon. ID: %s, gymId: %s' % (str(mon), str(gym)))
                        self.db_wrapper.submit_raid(str(gym), mon, lvl, None, raidend[2], 'MON', raidNo, captureTime,
                                                    unique_hash=self.uniqueHash, MonWithNoEgg=True)
                    else:
                        log.debug('[Crop: ' + str(raidNo) + ' (' + str(self.uniqueHash) + ') ] ' +
                                  'start_detect: Found Raidhash with an mon - fast submit')
                        log.debug('[Crop: ' + str(raidNo) + ' (' + str(self.uniqueHash) + ') ] ' +
                                  'start_detect: Submitting mon. ID: %s, gymId: %s' % (str(mon), str(gym)))
                        self.db_wrapper.submit_raid(str(gym), mon, lvl, None, None, 'MON', raidNo, captureTime,
                                                    unique_hash=self.uniqueHash)

                self.imageHash(raidhashPic, raidHash, False, 'raid', raidNo)
                os.remove(filenameOfCrop)
                os.remove(raidhashPic)
                log.debug('[Crop: ' + str(raidNo) + ' (' +
                          str(self.uniqueHash) + ') ] ' + 'start_detect: Finished')
                return True
            else:
                log.debug('[Crop: ' + str(raidNo) + ' (' + str(self.uniqueHash) +
                          ') ] ' + 'start_detect: detected Level not Hash Level')

        if raidlevel is None:
            log.error('[Crop: ' + str(raidNo) + ' (' + str(self.uniqueHash) + ') ] ' +
                      'start_detect: Could not determine raidlevel. Filename of Crop: %s' % (filenameOfCrop))
            os.remove(filenameOfCrop)
            os.remove(raidhashPic)
            return True

        if eggfound:
            log.debug('[Crop: ' + str(raidNo) + ' (' + str(self.uniqueHash) +
                      ') ] ' + 'start_detect: Found the crop to contain an egg')
            eggId = eggIdsByLevel[int(raidlevel) - 1]

        if not eggfound:
            log.debug('[Crop: ' + str(raidNo) + ' (' + str(self.uniqueHash) + ') ] ' +
                      'start_detect: Found the crop to contain a raidboss, lets see what boss it is')
            monFound = self.detectRaidBoss(img, raidlevel, hash, raidNo)
            if not monFound[0]:
                # we could not determine the mon... let's move the crop to unknown and stop analysing
                log.warning('[Crop: ' + str(raidNo) + ' (' + str(self.uniqueHash) + ') ] ' +
                            'start_detect: Could not determine mon in crop, aborting and moving crop to unknown')
                monUnkPic = os.path.join(self.tempPath, str(
                    hash) + "_unkmon" + str(raidNo) + ".jpg")
                cv2.imwrite(monUnkPic, img)
                self.unknownfound(monUnkPic, 'mon', False, raidNo,
                                  hash, captureTime, False, captureLat, captureLng)
                log.warning('[Crop: ' + str(raidNo) + ' (' + str(self.uniqueHash) + ') ] ' +
                            'start_detect: could not determine mon, aborting analysis')
                os.remove(raidhashPic)
                os.remove(monUnkPic)
                os.remove(filenameOfCrop)
                return True
            log.debug('[Crop: ' + str(raidNo) + ' (' +
                      str(self.uniqueHash) + ') ] ' + 'start_detect: Scanning Gym')
            gymId = self.detectGym(
                raidhashPic, hash, raidNo, captureLat, captureLng, radius, monFound[0])

        else:
            # let's get the gym we're likely scanning the image of
            gymId = self.detectGym(
                raidhashPic, hash, raidNo, captureLat, captureLng, radius)
            # gymId is either None for Gym not found or contains the gymId as String

        if gymId == 'dummy':
            os.remove(raidhashPic)
            os.remove(filenameOfCrop)
            log.warning('[Crop: ' + str(raidNo) + ' (' + str(self.uniqueHash) + ') ] ' +
                        'start_detect: determine dummy pic, aborting analysis')
            return True

        if gymId is None:
            # gym unknown...
            log.warning('[Crop: ' + str(raidNo) + ' (' + str(self.uniqueHash) + ') ] ' +
                        'start_detect: Could not determine gym, aborting analysis')
            os.remove(filenameOfCrop)
            os.remove(raidhashPic)
            log.debug('[Crop: ' + str(raidNo) + ' (' +
                      str(self.uniqueHash) + ') ] ' + 'start_detect: finished')
            return True  # return true since a raid is present, we just couldn't find the correct gym

        if eggfound:
            log.debug('[Crop: ' + str(raidNo) + ' (' + str(self.uniqueHash) + ') ] ' +
                      'start_detect: Found egg level %s starting at %s and ending at %s. GymID: %s' % (raidlevel, raidstart, raidend, gymId))
            submitStatus = self.db_wrapper.submit_raid(str(gymId), None, raidlevel, raidstart, raidend, 'EGG', raidNo,
                                                       captureTime, unique_hash=self.uniqueHash)
            # if submitStatus:
            raidHashJson = self.encodeHashJson(gymId, raidlevel, False, raidNo)
            log.debug('[Crop: ' + str(raidNo) + ' (' + str(self.uniqueHash) + ') ] ' +
                      'start_detect: Adding Raidhash to Database: ' + str(raidHashJson))
            self.imageHash(raidhashPic, raidHashJson, False, 'raid', raidNo)

        else:
            log.debug('[Crop: ' + str(raidNo) + ' (' + str(self.uniqueHash) +
                      ') ] ' + 'start_detect: Checking for Endtime')
            if not self.db_wrapper.read_raid_endtime(str(gymId), raidNo, unique_hash=self.uniqueHash):
                log.debug('[Crop: ' + str(raidNo) + ' (' + str(self.uniqueHash) +
                          ') ] ' + 'start_detect: No existing Egg found')
                raidend = self.detectRaidEndtimer(img, hash, raidNo, radius)
                if raidend[1]:
                    log.debug('[Crop: ' + str(raidNo) + ' (' + str(self.uniqueHash) + ') ] ' +
                              'start_detect: Submitting mon without egg. ID: %s, gymId: %s' % (str(monFound[0]), str(gymId)))
                    submitStatus = self.db_wrapper.submit_raid(str(gymId), monFound[0], raidlevel, None, raidend[2],
                                                               'MON', raidNo, captureTime, unique_hash=self.uniqueHash,
                                                               MonWithNoEgg=True)
                else:
                    log.debug('[Crop: ' + str(raidNo) + ' (' + str(self.uniqueHash) + ') ] ' +
                              'start_detect: Submitting mon without raidend. ID: %s, gymId: %s' % (str(monFound[0]), str(gymId)))
                    submitStatus = self.db_wrapper.submit_raid(str(gymId), monFound[0], raidlevel, None, None, 'MON',
                                                               raidNo, captureTime, unique_hash=self.uniqueHash)
            else:
                log.debug('[Crop: ' + str(raidNo) + ' (' + str(self.uniqueHash) + ') ] ' +
                          'start_detect: Submitting mon with previously reported endtime. ID: %s, gymId: %s' % (str(monFound[0]), str(gymId)))
                submitStatus = self.db_wrapper.submit_raid(str(gymId), monFound[0], raidlevel, None, None, 'MON',
                                                           raidNo, captureTime, unique_hash=self.uniqueHash)

            raidHashJson = self.encodeHashJson(
                gymId, raidlevel, monFound[0], raidNo)
            log.debug('[Crop: ' + str(raidNo) + ' (' + str(self.uniqueHash) + ') ] ' +
                      'start_detect: Adding Raidhash to Database: ' + str(raidHashJson))
            self.imageHash(raidhashPic, raidHashJson, False, 'raid', raidNo)

        self.unknownfound(raidhashPic, 'raid', False, raidNo,
                          hash, False, genRaidHash, '0', '0')

        os.remove(raidhashPic)
        os.remove(filenameOfCrop)

        log.debug('[Crop: ' + str(raidNo) + ' (' +
                  str(self.uniqueHash) + ') ] ' + 'start_detect: Finished')
        return True

    def dhash(self, image, raidNo, hash_size=8):
                # Grayscale and shrink the image in one step.

        h = str(imagehash.dhash(image))
        return h

        image = image.convert('L').resize(
            (hash_size + 1, hash_size),
            Image.ANTIALIAS,
        )
        pixels = list(image.getdata())
        # Compare adjacent pixels.
        difference = []
        for row in xrange(hash_size):
            for col in xrange(hash_size):
                pixel_left = image.getpixel((col, row))
                pixel_right = image.getpixel((col + 1, row))
                difference.append(pixel_left > pixel_right)
        # Convert the binary array to a hexadecimal string.
            decimal_value = 0
            hex_string = []
            for index, value in enumerate(difference):
                if value:
                    decimal_value += 2**(index % 8)
                if (index % 8) == 7:
                    hex_string.append(hex(decimal_value)[2:].rjust(2, '0'))
                    decimal_value = 0

        hashValue = ''.join(hex_string)
        log.debug('[Crop: ' + str(raidNo) + ' (' + str(self.uniqueHash) +
                  ') ] ' + 'ImageHash: Generated Image Hash: ' + str(hashValue))
        return hashValue

    def imageHashExists(self, image, zoom, type, raidNo, x1=0.30, x2=0.62, y1=0.62, y2=1.23, radius=0, hashSize=8):
        image2 = cv2.imread(image, 3)
        image2 = cv2.cvtColor(image2, cv2.COLOR_BGR2GRAY)
        if zoom:
            x1 = int(round(radius*2*0.03)+(radius*x1))
            x2 = int(round(radius*2*0.03)+(radius*x2))
            y1 = int(round(radius*2*0.03)+(radius*y1))
            y2 = int(round(radius*2*0.03)+(radius*y2))
            crop = image2[int(y1):int(y2), int(x1):int(x2)]
        else:
            crop = image2

        tempHash = os.path.join(self.tempPath, str(
            time.time()) + "_" + str(raidNo) + "temphash_check.jpg")
        cv2.imwrite(tempHash, crop)
        hashPic = Image.open(tempHash)
        imageHash = self.dhash(hashPic, raidNo)

        os.remove(tempHash)

        if type == 'raid':
            distance = 4
        else:
            distance = 4

        existHash = self.db_wrapper.check_for_hash(str(imageHash), str(type), raidNo, distance=distance,
                                                   unique_hash=self.uniqueHash)

        log.debug('[Crop: ' + str(raidNo) + ' (' + str(self.uniqueHash) +
                  ') ] ' + 'imageHashExists: Hash found: %s' % existHash[1])
        return existHash[1]

    def imageHash(self, image, id, zoom, type, raidNo, x1=0.30, x2=0.62, y1=0.62, y2=1.23, radius=0, hashSize=8):
        image2 = cv2.imread(image, 3)
        image2 = cv2.cvtColor(image2, cv2.COLOR_BGR2GRAY)
        if zoom:
            x1 = int(round(radius*2*0.03)+(radius*x1))
            x2 = int(round(radius*2*0.03)+(radius*x2))
            y1 = int(round(radius*2*0.03)+(radius*y1))
            y2 = int(round(radius*2*0.03)+(radius*y2))
            crop = image2[int(y1):int(y2), int(x1):int(x2)]
        else:
            crop = image2

        tempHash = os.path.join(self.tempPath, str(
            time.time()) + "_" + str(raidNo) + "temphash_new.jpg")
        cv2.imwrite(tempHash, crop)
        hashPic = Image.open(tempHash)
        imageHash = self.dhash(hashPic, raidNo)

        log.debug('[Crop: ' + str(raidNo) + ' (' +
                  str(self.uniqueHash) + ') ] ' + 'imageHash: ' + str(imageHash))

        os.remove(tempHash)

        if type == 'raid':
            distance = 4
        else:
            distance = 4

        existHash = self.db_wrapper.check_for_hash(str(imageHash), str(type), raidNo, distance=distance,
                                                   unique_hash=self.uniqueHash)
        if existHash[0]:
            log.debug('[Crop: ' + str(raidNo) + ' (' + str(self.uniqueHash) + ') ] ' +
                      'imageHash: Hash already in Database: ' + str(existHash[2]))
            self.db_wrapper.insert_hash(str(existHash[2]), str(
                type), str(id), raidNo, unique_hash=self.uniqueHash)
            return str(existHash[2])
        else:
            log.debug('[Crop: ' + str(raidNo) + ' (' + str(self.uniqueHash) + ') ] ' +
                      'imageHash: Adding Hash to Database: ' + str(imageHash))
            self.db_wrapper.insert_hash(str(imageHash), str(
                type), str(id), raidNo, unique_hash=self.uniqueHash)
            return str(imageHash)

    def getImageHash(self, image, zoom, raidNo, type, x1=0.30, x2=0.62, y1=0.62, y2=1.23, radius=0, hashSize=8):
        image2 = cv2.imread(image, 3)
        image2 = cv2.cvtColor(image2, cv2.COLOR_BGR2GRAY)
        if zoom:
            x1 = int(round(radius*2*0.03)+(radius*x1))
            x2 = int(round(radius*2*0.03)+(radius*x2))
            y1 = int(round(radius*2*0.03)+(radius*y1))
            y2 = int(round(radius*2*0.03)+(radius*y2))
            crop = image2[int(y1):int(y2), int(x1):int(x2)]
        else:
            crop = image2

        tempHash = os.path.join(self.tempPath, str(
            time.time()) + "_" + str(raidNo) + "temphash_new.jpg")
        cv2.imwrite(tempHash, crop)
        hashPic = Image.open(tempHash)
        imageHash = self.dhash(hashPic, raidNo)

        log.debug('[Crop: ' + str(raidNo) + ' (' + str(self.uniqueHash) +
                  ') ] ' + 'getImageHash: ' + str(imageHash))
        os.remove(tempHash)

        if type == 'raid':
            distance = 4
        else:
            distance = 4

        existHash = self.db_wrapper.check_for_hash(str(imageHash), str(type), raidNo, distance=distance,
                                                   unique_hash=self.uniqueHash)
        if existHash[0]:
            log.debug('[Crop: ' + str(raidNo) + ' (' + str(self.uniqueHash) + ') ] ' +
                      'getImageHash: Hash already in Database: ' + str(existHash[2]))
            return str(existHash[2])
        else:
            log.debug('[Crop: ' + str(raidNo) + ' (' + str(self.uniqueHash) + ') ] ' +
                      'getImageHash: Hash not in Database: ' + str(imageHash))
            return str(imageHash)

    def checkHourMin(self, hour_min):
        hour_min[0] = hour_min[0].replace(
            'O', '0').replace('o', '0').replace('A', '4')
        hour_min[1] = hour_min[1].replace(
            'O', '0').replace('o', '0').replace('A', '4')
        if (hour_min[0]).isnumeric() == True and (hour_min[1]).isnumeric() == True:
            return True, hour_min
        else:
            return False, hour_min

    @staticmethod
    def checkHourMinSec(hour_min_sec):
        if hour_min_sec is None:
            return False, None
        hour_min_sec[0] = hour_min_sec[0].replace(
            'O', '0').replace('o', '0').replace('A', '4')
        hour_min_sec[1] = hour_min_sec[1].replace(
            'O', '0').replace('o', '0').replace('A', '4')
        hour_min_sec[2] = hour_min_sec[2].replace(
            'O', '0').replace('o', '0').replace('A', '4')
        if (hour_min_sec[0]).isnumeric() and (hour_min_sec[1]).isnumeric() \
                and (hour_min_sec[2]).isnumeric():
            return True, hour_min_sec
        else:
            return False, hour_min_sec

    # returns UTC timestamp
    def getHatchTime(self, data, raidNo):
        zero = datetime.datetime.now().replace(
            hour=0, minute=0, second=0, microsecond=0)
        unix_zero = time.mktime(zero.timetuple())
        hour_min_divider = data.find(':')
        if hour_min_divider is None or hour_min_divider == -1:
            return False

        # TODO: think about only one big fat regex noone wants to read lateron
        am_found = re.search(r"[a|A]\w+", data)
        pm_found = re.search(r"[p|P]\w+", data)
        hour_min = re.search(r"([\d]{1,2}:[\d]{1,2})", data)

        if hour_min is None:
            log.fatal('[Crop: ' + str(raidNo) + ' (' + str(self.uniqueHash) +
                      ') ]' + 'getHatchTime: Could not locate a HH:MM')
            return False
        else:
            hour_min = hour_min.group(1).split(':')

        ret, hour_min = self.checkHourMin(hour_min)
        if not ret:
            return False

        if am_found:
            log.debug('[Crop: ' + str(raidNo) + ' (' +
                      str(self.uniqueHash) + ') ] ' + 'getHatchTime: Found AM')
            return int(unix_zero)+int(hour_min[0])*3600+int(hour_min[1])*60
        elif pm_found:
            log.debug('[Crop: ' + str(raidNo) + ' (' +
                      str(self.uniqueHash) + ') ] ' + 'getHatchTime: Found PM')
            if hour_min[0] == '12':
                return int(unix_zero)+int(hour_min[0])*3600+int(hour_min[1])*60
            else:
                return int(unix_zero)+(int(hour_min[0])+12)*3600+int(hour_min[1])*60
        else:
            log.debug('[Crop: ' + str(raidNo) + ' (' +
                      str(self.uniqueHash) + ') ] ' + 'getHatchTime: Found EU Time')
            return int(unix_zero)+int(hour_min[0])*3600+int(hour_min[1])*60

    def getEndTime(self, data, raidNo):
        zero = datetime.datetime.now()
        unix_zero = time.mktime(zero.timetuple())
        hour_min_divider = data.find(':')
        log.debug('[Crop: ' + str(raidNo) + ' (' + str(self.uniqueHash) +
                  ') ] ' + 'getHatchTime: :Count: ' + str(data.count(':')))
        if data.count(':') < 2:
            log.error('[Crop: ' + str(raidNo) + ' (' + str(self.uniqueHash) +
                      ') ] ' + 'getHatchTime: Detect wrong Endtimer of Raid')
            return False
        if hour_min_divider != -1:
            data = data.replace('~', '').replace('-', '').replace(' ', '')
            hour_min = data.split(':')
            ret, hour_min = self.checkHourMinSec(hour_min)
            if ret:
                return int(unix_zero)+int(hour_min[0])*3600+int(hour_min[1])*60+int(hour_min[2])
            else:
                return False
        else:
            return False
