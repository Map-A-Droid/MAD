import math
import os
import os.path
import time
from multiprocessing.pool import ThreadPool
from typing import Optional, List, Tuple
import cv2
import numpy as np
import pytesseract
from PIL import Image
from pytesseract import Output
from mapadroid.ocr.matching_trash import trash_image_matching
from mapadroid.ocr.screen_type import ScreenType
from mapadroid.utils.logging import get_logger, LoggerEnums, get_origin_logger


logger = get_logger(LoggerEnums.ocr)


class PogoWindows:
    def __init__(self, temp_dir_path, thread_count: int):
        if not os.path.exists(temp_dir_path):
            os.makedirs(temp_dir_path)
            logger.info('PogoWindows: Temp directory created')
        self.temp_dir_path = temp_dir_path
        self.__thread_pool = ThreadPool(processes=thread_count)

        # screendetection
        self._ScreenType: dict = {}
        self._ScreenType[1]: list = ['Geburtdatum', 'birth.', 'naissance.', 'date']
        self._ScreenType[2]: list = ['ZURUCKKEHRENDER', 'ZURÜCKKEHRENDER', 'GAME', 'FREAK', 'SPIELER']
        self._ScreenType[3]: list = ['Google', 'Facebook']
        self._ScreenType[4]: list = ['Benutzername', 'Passwort', 'Username', 'Password', 'DRESSEURS']
        self._ScreenType[5]: list = ['Authentifizierung', 'fehlgeschlagen', 'Unable', 'authenticate',
                                     'Authentification', 'Essaye']
        self._ScreenType[6]: list = ['RETRY', 'TRY', 'DIFFERENT', 'ACCOUNT',
                                     'ANDERES', 'KONTO', 'VERSUCHEN',
                                     'AUTRE', 'AUTORISER']
        self._ScreenType[7]: list = ['incorrect.', 'attempts', 'falsch.', 'gesperrt']
        self._ScreenType[8]: list = ['Spieldaten', 'abgerufen', 'lecture', 'depuis', 'server', 'data']
        self._ScreenType[12]: list = ['Events,', 'Benachrichtigungen', 'Einstellungen', 'events,', 'offers,',
                                      'notifications', 'évenements,', 'evenements,', 'offres']
        self._ScreenType[14]: list = ['kompatibel', 'compatible', 'OS', 'software', 'device', 'Gerät',
                                      'Betriebssystem',
                                      'logiciel']
        self._ScreenType[15]: list = ['continuer...', 'aktualisieren?', 'now?', 'Aktualisieren',
                                      'Aktualisieren,',
                                      'aktualisieren', 'update', 'continue...', 'Veux-tu', 'Fais',
                                      'continuer']
        self._ScreenType[16]: list = ['modified', 'client', 'Strike', 'suspension', 'third-party',
                                      'modifizierte', 'Verstoß', 'Sperrung', 'Drittpartei']
        self._ScreenType[17]: list = ['Suspension', 'suspended', 'violating', 'days', ]
        self._ScreenType[18]: list = ['Termination', 'terminated', 'permanently']
        self._ScreenType[21]: list = ['GPS', 'signal', 'GPS-Signal', '(11)', 'introuvable.',
                                      'found.', 'gefunden.', 'Signal', 'geortet', 'detect', '(12)']
        self._ScreenType[23]: list = ['CLUB', 'KIDS']

    def __read_circle_count(self, filename, identifier, ratio, communicator, xcord=False, crop=False,
                            click=False,
                            canny=False, secondratio=False):
        origin_logger = get_origin_logger(logger, origin=identifier)
        origin_logger.debug2("__read_circle_count: Reading circles")

        try:
            screenshot_read = cv2.imread(filename)
        except Exception:
            origin_logger.error("Screenshot corrupted")
            return -1

        if screenshot_read is None:
            origin_logger.error("Screenshot corrupted")
            return -1

        height, width, _ = screenshot_read.shape

        if crop:
            screenshot_read = screenshot_read[int(height) - int(int(height / 4)):int(height),
                                              int(int(width) / 2) - int(int(width) / 8):int(int(width) / 2) + int(
                                              int(width) / 8)]

        origin_logger.debug("__read_circle_count: Determined screenshot scale: {} x {}", height, width)
        gray = cv2.cvtColor(screenshot_read, cv2.COLOR_BGR2GRAY)
        # detect circles in the image

        if not secondratio:
            radius_min = int((width / float(ratio) - 3) / 2)
            radius_max = int((width / float(ratio) + 3) / 2)
        else:
            radius_min = int((width / float(ratio) - 3) / 2)
            radius_max = int((width / float(secondratio) + 3) / 2)
        if canny:
            gray = cv2.GaussianBlur(gray, (3, 3), 0)
            gray = cv2.Canny(gray, 100, 50, apertureSize=3)

        origin_logger.debug("__read_circle_count: Detect radius of circle: Min {} / Max {}", radius_min, radius_max)
        circles = cv2.HoughCircles(gray, cv2.HOUGH_GRADIENT, 1, width / 8, param1=100, param2=15,
                                   minRadius=radius_min,
                                   maxRadius=radius_max)
        circle = 0
        # ensure at least some circles were found
        if circles is not None:
            # convert the (x, y) coordinates and radius of the circles to integers
            circles = np.round(circles[0, :]).astype("int")
            # loop over the (x, y) coordinates and radius of the circles
            for (pos_x, pos_y, radius) in circles:

                if not xcord:
                    circle += 1
                    if click:
                        origin_logger.debug('__read_circle_count: found Circle - click it')
                        communicator.click(width / 2, ((int(height) - int(height / 4.5))) + pos_y)
                        time.sleep(2)
                else:
                    if pos_x >= (width / 2) - 100 and pos_x <= (width / 2) + 100 and pos_y >= (height - (height / 3)):
                        circle += 1
                        if click:
                            origin_logger.debug('__read_circle_count: found Circle - click on: it')
                            communicator.click(width / 2, ((int(height) - int(height / 4.5))) + pos_y)
                            time.sleep(2)

            origin_logger.debug("__read_circle_count: Determined screenshot to have {} Circle.", circle)
            return circle
        else:
            origin_logger.debug("__read_circle_count: Determined screenshot to have 0 Circle")
            return -1

    def get_trash_click_positions(self, origin, filename, full_screen=False):
        origin_logger = get_origin_logger(logger, origin=origin)
        if not os.path.isfile(filename):
            origin_logger.error("get_trash_click_positions: {} does not exist", filename)
            return None

        return self.__thread_pool.apply_async(trash_image_matching, (origin, filename, full_screen,)).get()

    def look_for_button(self, origin, filename, ratiomin, ratiomax, communicator, upper: bool = False):
        origin_logger = get_origin_logger(logger, origin=origin)
        if not os.path.isfile(filename):
            origin_logger.error("look_for_button: {} does not exist", filename)
            return False

        return self.__thread_pool.apply_async(self.__internal_look_for_button,
                                              (origin, filename, ratiomin, ratiomax, communicator, upper)).get()

    def __internal_look_for_button(self, origin, filename, ratiomin, ratiomax, communicator, upper):
        origin_logger = get_origin_logger(logger, origin=origin)
        origin_logger.debug("lookForButton: Reading lines")
        min_distance_to_middle = None
        try:
            screenshot_read = cv2.imread(filename)
            gray = cv2.cvtColor(screenshot_read, cv2.COLOR_BGR2GRAY)
        except cv2.error:
            origin_logger.error("Screenshot corrupted")
            return False

        if screenshot_read is None:
            origin_logger.error("Screenshot corrupted")
            return False

        height, width, _ = screenshot_read.shape
        _widthold = float(width)
        origin_logger.debug("lookForButton: Determined screenshot scale: {} x {}", height, width)

        # resize for better line quality
        height, width = gray.shape
        factor = width / _widthold

        gray = cv2.GaussianBlur(gray, (3, 3), 0)
        edges = cv2.Canny(gray, 50, 200, apertureSize=3)
        # checking for all possible button lines

        max_line_length = (width / ratiomin) + (width * 0.18)
        origin_logger.debug("lookForButton: MaxLineLength: {}", max_line_length)
        min_line_length = (width / ratiomax) - (width * 0.02)
        origin_logger.debug("lookForButton: MinLineLength: {}", min_line_length)

        kernel = np.ones((2, 2), np.uint8)
        edges = cv2.morphologyEx(edges, cv2.MORPH_GRADIENT, kernel)

        num_lines = 0
        lines = []
        lines = cv2.HoughLinesP(edges, rho=1, theta=math.pi / 180, threshold=90, minLineLength=min_line_length,
                                maxLineGap=5)
        if lines is None:
            return False

        lines = self.check_lines(lines, height)

        _last_y = 0
        for line in lines:
            line = [line]
            for x1, y1, x2, y2 in line:

                if y1 == y2 and x2 - x1 <= max_line_length and x2 - x1 >= min_line_length \
                        and y1 > height / 3 \
                        and (x2 - x1) / 2 + x1 < width / 2 + 50 and (x2 - x1) / 2 + x1 > width / 2 - 50:

                    num_lines += 1
                    min_distance_to_middle_tmp = y1 - (height / 2)
                    if upper:
                        if min_distance_to_middle is None:
                            min_distance_to_middle = min_distance_to_middle_tmp
                            click_y = y1 + 50
                            _last_y = y1
                            _x1 = x1
                            _x2 = x2
                        else:
                            if min_distance_to_middle_tmp < min_distance_to_middle:
                                click_y = _last_y + ((y1 - _last_y) / 2)
                                _last_y = y1
                                _x1 = x1
                                _x2 = x2

                    else:
                        click_y = _last_y + ((y1 - _last_y) / 2)
                        _last_y = y1
                        _x1 = x1
                        _x2 = x2
                    origin_logger.debug("lookForButton: Found Buttonline Nr. {} - Line lenght: {}px Coords - X: {} {} "
                                        "Y: {} {}", num_lines, x2 - x1, x1, x2, y1, y1)

        if 1 < num_lines <= 6:
            # recalculate click area for real resolution
            click_x = int(((width - _x2) + ((_x2 - _x1) / 2)) /
                          round(factor, 2))
            click_y = int(click_y)
            origin_logger.debug('lookForButton: found Button - click on it')
            communicator.click(click_x, click_y)
            time.sleep(4)
            return True

        elif num_lines > 6:
            origin_logger.debug('lookForButton: found to much Buttons :) - close it')
            communicator.click(int(width - (width / 7.2)),
                               int(height - (height / 12.19)))
            time.sleep(4)

            return True

        origin_logger.debug('lookForButton: did not found any Button')
        return False

    def check_lines(self, lines, height):
        temp_lines = []
        sort_lines = []
        old_y1 = 0
        index = 0

        for line in lines:
            for x1, y1, x2, y2 in line:
                temp_lines.append([y1, y2, x1, x2])

        temp_lines = np.array(temp_lines)
        sort_arr = (temp_lines[temp_lines[:, 0].argsort()])

        button_value = height / 40

        for line in sort_arr:
            if int(old_y1 + int(button_value)) < int(line[0]):
                if int(line[0]) == int(line[1]):
                    sort_lines.append([line[2], line[0], line[3], line[1]])
                    old_y1 = line[0]
            index += 1

        return np.asarray(sort_lines, dtype=np.int32)

    def __check_raid_line(self, filename, identifier, communicator, left_side=False, clickinvers=False):
        origin_logger = get_origin_logger(logger, origin=identifier)
        origin_logger.debug("__check_raid_line: Reading lines")
        if left_side:
            origin_logger.debug("__check_raid_line: Check nearby open ")
        try:
            screenshot_read = cv2.imread(filename)
        except Exception:
            origin_logger.error("Screenshot corrupted")
            return False
        if screenshot_read is None:
            origin_logger.error("Screenshot corrupted")
            return False

        if self.__read_circle_count(os.path.join('', filename), identifier, float(11), communicator,
                                    xcord=False,
                                    crop=True,
                                    click=False, canny=True) == -1:
            origin_logger.debug("__check_raid_line: Not active")
            return False

        height, width, _ = screenshot_read.shape
        screenshot_read = screenshot_read[int(height / 2) - int(height / 3):int(height / 2) + int(height / 3),
                                          int(0):int(width)]
        gray = cv2.cvtColor(screenshot_read, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (5, 5), 0)
        origin_logger.debug("__check_raid_line: Determined screenshot scale: {} x {}", height, width)
        edges = cv2.Canny(gray, 50, 150, apertureSize=3)
        max_line_length = width / 3.30 + width * 0.03
        origin_logger.debug("__check_raid_line: MaxLineLength: {}", max_line_length)
        min_line_length = width / 6.35 - width * 0.03
        origin_logger.debug("__check_raid_line: MinLineLength: {}", min_line_length)
        lines = cv2.HoughLinesP(edges, rho=1, theta=math.pi / 180, threshold=70, minLineLength=min_line_length,
                                maxLineGap=2)
        if lines is None:
            return False
        for line in lines:
            for x1, y1, x2, y2 in line:
                if not left_side:
                    if y1 == y2 and (x2 - x1 <= max_line_length) and (
                            x2 - x1 >= min_line_length) and x1 > width / 2 and x2 > width / 2 and y1 < (
                            height / 2):
                        origin_logger.debug("__check_raid_line: Raid-tab is active - Line length: {}px "
                                            "Coords - x: {} {} Y: {} {}", x2 - x1, x1, x2, y1, y2)
                        return True
                else:
                    if y1 == y2 and (x2 - x1 <= max_line_length) and (
                            x2 - x1 >= min_line_length) and (
                            (x1 < width / 2 and x2 < width / 2) or (
                            x1 < width / 2 and x2 > width / 2)) and y1 < (
                            height / 2):
                        origin_logger.debug("__check_raid_line: Nearby is active - but not Raid-Tab")
                        if clickinvers:
                            raidtab_x = int(width - (x2 - x1))
                            raidtab_y = int(
                                (int(height / 2) - int(height / 3) + y1) * 0.9)
                            origin_logger.debug('__check_raid_line: open Raid-Tab')
                            communicator.click(raidtab_x, raidtab_y)
                            time.sleep(3)
                        return True
        origin_logger.debug("__check_raid_line: Not active")
        return False

    def __check_close_present(self, filename, identifier, communicator, radiusratio=12, x_coord=True):
        origin_logger = get_origin_logger(logger, origin=identifier)
        if not os.path.isfile(filename):
            origin_logger.warning("__check_close_present: {} does not exist", filename)
            return False

        try:
            image = cv2.imread(filename)
            height, width, _ = image.shape
        except Exception as e:
            origin_logger.error("Screenshot corrupted: {}", e)
            return False

        imwrite_status = cv2.imwrite(os.path.join(self.temp_dir_path,
                                     str(identifier) + '_exitcircle.jpg'), image)
        if not imwrite_status:
            origin_logger.error("Could not save file: {} - check permissions and path",
                                os.path.join(self.temp_dir_path, str(identifier) + '_exitcircle.jpg'))
            return False

        if self.__read_circle_count(os.path.join(self.temp_dir_path, str(identifier) + '_exitcircle.jpg'),
                                    identifier,
                                    float(radiusratio), communicator, xcord=False, crop=True, click=True,
                                    canny=True) > 0:
            return True

    def check_close_except_nearby_button(self, filename, identifier, communicator, close_raid=False):
        origin_logger = get_origin_logger(logger, origin=identifier)
        if not os.path.isfile(filename):
            origin_logger.error("check_close_except_nearby_button: {} does not exist", filename)
            return False

        return self.__thread_pool.apply_async(self.__internal_check_close_except_nearby_button,
                                              (filename, identifier, communicator, close_raid)).get()

    # checks for X button on any screen... could kill raidscreen, handle properly
    def __internal_check_close_except_nearby_button(self, filename, identifier, communicator,
                                                    close_raid=False):
        origin_logger = get_origin_logger(logger, origin=identifier)
        origin_logger.debug("__internal_check_close_except_nearby_button: Checking close except nearby with: file {}",
                            filename)
        try:
            screenshot_read = cv2.imread(filename)
        except cv2.error:
            origin_logger.error("Screenshot corrupted")
            origin_logger.debug("__internal_check_close_except_nearby_button: Screenshot corrupted...")
            return False
        if screenshot_read is None:
            origin_logger.error("__internal_check_close_except_nearby_button: Screenshot corrupted")
            return False

        if not close_raid:
            origin_logger.debug("__internal_check_close_except_nearby_button: Raid is not to be closed...")
            if not os.path.isfile(filename) \
               or self.__check_raid_line(filename, identifier, communicator) \
               or self.__check_raid_line(filename, identifier, communicator, True):
                # file not found or raid tab present
                origin_logger.debug("__internal_check_close_except_nearby_button: Not checking for close button (X). "
                                    "Input wrong OR nearby window open")
                return False
        origin_logger.debug("__internal_check_close_except_nearby_button: Checking for close button (X). Input wrong "
                            "OR nearby window open")

        if self.__check_close_present(filename, identifier, communicator, 10, True):
            origin_logger.debug("Found close button (X). Closing the window - Ratio: 10")
            return True
        if self.__check_close_present(filename, identifier, communicator, 11, True):
            origin_logger.debug("Found close button (X). Closing the window - Ratio: 11")
            return True
        elif self.__check_close_present(filename, identifier, communicator, 12, True):
            origin_logger.debug("Found close button (X). Closing the window - Ratio: 12")
            return True
        elif self.__check_close_present(filename, identifier, communicator, 14, True):
            origin_logger.debug("Found close button (X). Closing the window - Ratio: 14")
            return True
        elif self.__check_close_present(filename, identifier, communicator, 13, True):
            origin_logger.debug("Found close button (X). Closing the window - Ratio: 13")
            return True
        else:
            origin_logger.debug("Could not find close button (X).")
            return False

    def get_inventory_text(self, filename, identifier, x1, x2, y1, y2) -> Optional[str]:
        origin_logger = get_origin_logger(logger, origin=identifier)
        if not os.path.isfile(filename):
            origin_logger.error("get_inventory_text: {} does not exist", filename)
            return None

        return self.__thread_pool.apply_async(self.__internal_get_inventory_text,
                                              (filename, identifier, x1, x2, y1, y2)).get()

    def __internal_get_inventory_text(self, filename, identifier, x1, x2, y1, y2) -> Optional[str]:
        origin_logger = get_origin_logger(logger, origin=identifier)
        screenshot_read = cv2.imread(filename)
        temp_path_item = self.temp_dir_path + "/" + str(identifier) + "_inventory.png"
        height = x1 - x2
        width = y1 - y2
        gray = cv2.cvtColor(screenshot_read, cv2.COLOR_BGR2GRAY)
        gray = gray[int(y2):(int(y2) + int(width)), int(x2):(int(x2) + int(height))]
        scale_percent = 200  # percent of original size
        scaled_width = int(gray.shape[1] * scale_percent / 100)
        scaled_height = int(gray.shape[0] * scale_percent / 100)
        dim = (scaled_width, scaled_height)

        # resize image
        gray = cv2.resize(gray, dim, interpolation=cv2.INTER_AREA)
        imwrite_status = cv2.imwrite(temp_path_item, gray)
        if not imwrite_status:
            origin_logger.error("Could not save file: {} - check permissions and path", temp_path_item)
            return None
        try:
            with Image.open(temp_path_item) as im:
                try:
                    text = pytesseract.image_to_string(im)
                except Exception as e:
                    origin_logger.error("Error running tesseract on inventory text: {}", e)
                    return None
        except (FileNotFoundError, ValueError) as e:
            origin_logger.error("Failed opening image {} with exception {}", temp_path_item, e)
            return None
        return text

    def check_pogo_mainscreen(self, filename, identifier):
        origin_logger = get_origin_logger(logger, origin=identifier)
        if not os.path.isfile(filename):
            origin_logger.error("check_pogo_mainscreen: {} does not exist", filename)
            return False

        return self.__thread_pool.apply_async(self.__internal_check_pogo_mainscreen,
                                              (filename, identifier)).get()

    def __internal_check_pogo_mainscreen(self, filename, identifier):
        origin_logger = get_origin_logger(logger, origin=identifier)
        origin_logger.debug("__internal_check_pogo_mainscreen: Checking close except nearby with: file {}", filename)
        mainscreen = 0
        try:
            screenshot_read = cv2.imread(filename)
        except Exception:
            origin_logger.error("Screenshot corrupted")
            logger.debug("__internal_check_pogo_mainscreen: Screenshot corrupted...")
            return False
        if screenshot_read is None:
            origin_logger.error("__internal_check_pogo_mainscreen: Screenshot corrupted")
            return False

        height, width, _ = screenshot_read.shape
        gray = screenshot_read[int(height) - int(round(height / 5)):int(height),
                               0: int(int(width) / 4)]
        _, width_, _ = gray.shape
        radius_min = int((width / float(6.8) - 3) / 2)
        radius_max = int((width / float(6) + 3) / 2)
        gray = cv2.GaussianBlur(gray, (3, 3), 0)
        gray = cv2.Canny(gray, 200, 50, apertureSize=3)
        circles = cv2.HoughCircles(gray, cv2.HOUGH_GRADIENT, 1, width / 8, param1=100, param2=15,
                                   minRadius=radius_min,
                                   maxRadius=radius_max)
        if circles is not None:
            circles = np.round(circles[0, :]).astype("int")
            for (pos_x, pos_y, radius) in circles:
                if pos_x < width_ - width_ / 3:
                    mainscreen += 1

        if mainscreen > 0:
            origin_logger.debug("Found avatar.")
            return True
        return False

    def get_screen_text(self, screenpath: str, identifier) -> Optional[dict]:
        origin_logger = get_origin_logger(logger, origin=identifier)
        if screenpath is None:
            origin_logger.error("get_screen_text: image does not exist")
            return None

        return self.__thread_pool.apply_async(self.__internal_get_screen_text,
                                              (screenpath, identifier)).get()

    def __internal_get_screen_text(self, screenpath: str, identifier) -> Optional[dict]:
        origin_logger = get_origin_logger(logger, origin=identifier)
        returning_dict: Optional[dict] = {}
        origin_logger.debug("get_screen_text: Reading screen text")

        try:
            with Image.open(screenpath) as frame:
                frame = frame.convert('LA')
                try:
                    returning_dict = pytesseract.image_to_data(frame, output_type=Output.DICT, timeout=40,
                                                               config='--dpi 70')
                except Exception as e:
                    origin_logger.error("Tesseract Error: {}. Exception: {}", returning_dict, e)
                    returning_dict = None
        except (FileNotFoundError, ValueError) as e:
            origin_logger.error("Failed opening image {} with exception {}", screenpath, e)
            return None

        if isinstance(returning_dict, dict):
            return returning_dict
        else:
            origin_logger.warning("Could not read text in image: {}", returning_dict)
            return None

    def most_frequent_colour(self, screenshot, identifier) -> Optional[List[int]]:
        origin_logger = get_origin_logger(logger, origin=identifier)
        if screenshot is None:
            origin_logger.error("get_screen_text: image does not exist")
            return None

        return self.__thread_pool.apply_async(self.__most_frequent_colour_internal,
                                              (screenshot, identifier)).get()

    def __most_frequent_colour_internal(self, image, identifier) -> Optional[List[int]]:
        origin_logger = get_origin_logger(logger, origin=identifier)
        origin_logger.debug("most_frequent_colour_internal: Reading screen text")
        try:
            with Image.open(image) as img:
                w, h = img.size
                pixels = img.getcolors(w * h)
                most_frequent_pixel = pixels[0]

                for count, colour in pixels:
                    if count > most_frequent_pixel[0]:
                        most_frequent_pixel = (count, colour)

                origin_logger.debug("Most frequent pixel on screen: {}", most_frequent_pixel[1])
        except (FileNotFoundError, ValueError) as e:
            origin_logger.error("Failed opening image {} with exception {}", image, e)
            return None

        return most_frequent_pixel[1]

    def screendetection_get_type_by_screen_analysis(self, image,
                                                    identifier) -> Optional[Tuple[ScreenType,
                                                                                  Optional[
                                                                                      dict], int, int, int]]:
        return self.__thread_pool.apply_async(self.__screendetection_get_type_internal,
                                              (image, identifier)).get()

    def __screendetection_get_type_internal(self, image,
                                            identifier) -> Optional[Tuple[ScreenType, Optional[dict], int, int, int]]:
        origin_logger = get_origin_logger(logger, origin=identifier)
        returntype: ScreenType = ScreenType.UNDEFINED
        globaldict: Optional[dict] = {}
        diff: int = 1
        origin_logger.debug("__screendetection_get_type_internal: Detecting screen type")

        texts = []
        try:
            with Image.open(image) as frame_org:
                width, height = frame_org.size

                origin_logger.debug("Screensize: W:{} x H:{}", width, height)

                if width < 1080:
                    origin_logger.info('Resize screen ...')
                    frame_org = frame_org.resize([int(2 * s) for s in frame_org.size], Image.ANTIALIAS)
                    diff: int = 2

                texts = [frame_org]
                for thresh in [200, 175, 150]:
                    fn = lambda x: 255 if x > thresh else 0  # noqa: E731
                    frame = frame_org.convert('L').point(fn, mode='1')
                    texts.append(frame)
                for text in texts:
                    try:
                        globaldict = pytesseract.image_to_data(text, output_type=Output.DICT, timeout=40,
                                                               config='--dpi 70')
                    except Exception as e:
                        origin_logger.error("Tesseract Error: {}. Exception: {}", globaldict, e)
                        globaldict = None
                    origin_logger.debug("Screentext: {}", globaldict)
                    if globaldict is None or 'text' not in globaldict:
                        continue
                    n_boxes = len(globaldict['text'])
                    for index in range(n_boxes):
                        if returntype != ScreenType.UNDEFINED:
                            break
                        if len(globaldict['text'][index]) > 3:
                            for screen_elem in self._ScreenType:
                                heightlimit = 0 if screen_elem == 21 else height / 4
                                if globaldict['top'][index] > heightlimit and globaldict['text'][index] in \
                                        self._ScreenType[screen_elem]:
                                    returntype = ScreenType(screen_elem)
                    if returntype != ScreenType.UNDEFINED:
                        break

                del texts
                frame.close()
        except (FileNotFoundError, ValueError) as e:
            origin_logger.error("Failed opening image {} with exception {}", image, e)
            return None

        return returntype, globaldict, width, height, diff
