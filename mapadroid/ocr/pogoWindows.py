import asyncio
import concurrent.futures
import math
import os
import os.path
from typing import List, Optional, Tuple

import cv2
import numpy as np
from loguru import logger

from mapadroid.ocr.matching_trash import trash_image_matching
from mapadroid.ocr.screen_type import ScreenType
from mapadroid.ocr.utils import check_pogo_mainscreen, screendetection_get_type_internal, most_frequent_colour_internal, \
    get_screen_text, get_inventory_text
from mapadroid.utils.AsyncioCv2 import AsyncioCv2
from mapadroid.utils.AsyncioOsUtil import AsyncioOsUtil


class PogoWindows:
    def __init__(self, temp_dir_path, thread_count: int):
        # TODO: move to init? This will block if called in asyncio loop
        if not os.path.exists(temp_dir_path):
            os.makedirs(temp_dir_path)
            logger.info('PogoWindows: Temp directory created')
        self.temp_dir_path = temp_dir_path
        self.__process_executor_pool: concurrent.futures.ThreadPoolExecutor = concurrent.futures.ThreadPoolExecutor(
            thread_count)
        # TODO: SHutdown pool...

    async def __read_circle_count(self, filename, identifier, ratio, communicator, xcord=False, crop=False,
                                  click=False,
                                  canny=False, secondratio=False):
        logger.debug2("__read_circle_count: Reading circles")

        try:
            screenshot_read = await AsyncioCv2.imread(filename)
        except Exception:
            logger.error("Screenshot corrupted")
            return -1

        if screenshot_read is None:
            logger.error("Screenshot corrupted")
            return -1

        height, width, _ = screenshot_read.shape

        if crop:
            screenshot_read = screenshot_read[int(height) - int(int(height / 4)):int(height),
                              int(int(width) / 2) - int(int(width) / 8):int(int(width) / 2) + int(
                                  int(width) / 8)]

        logger.debug("__read_circle_count: Determined screenshot scale: {} x {}", height, width)
        gray = await AsyncioCv2.cvtColor(screenshot_read, cv2.COLOR_BGR2GRAY)
        # detect circles in the image

        if not secondratio:
            radius_min = int((width / float(ratio) - 3) / 2)
            radius_max = int((width / float(ratio) + 3) / 2)
        else:
            radius_min = int((width / float(ratio) - 3) / 2)
            radius_max = int((width / float(secondratio) + 3) / 2)
        if canny:
            gray = await AsyncioCv2.GaussianBlur(gray, (3, 3), 0)
            gray = await AsyncioCv2.Canny(gray, 100, 50, apertureSize=3)

        logger.debug("__read_circle_count: Detect radius of circle: Min {} / Max {}", radius_min, radius_max)
        circles = await AsyncioCv2.HoughCircles(gray, cv2.HOUGH_GRADIENT, 1, width / 8, param1=100, param2=15,
                                                minRadius=radius_min,
                                                maxRadius=radius_max)
        circle = 0
        # ensure at least some circles were found
        if circles is not None:
            # convert the (x, y) coordinates and radius of the circles to integers
            circles_first_col = np.round(circles[0, :]).astype("int")
            # loop over the (x, y) coordinates and radius of the circles
            for (pos_x, pos_y, _) in circles_first_col:
                if not xcord:
                    circle += 1
                    if click:
                        logger.debug('__read_circle_count: found Circle - click it')
                        await communicator.click(width / 2, ((int(height) - int(height / 4.5))) + pos_y)
                        await asyncio.sleep(2)
                else:
                    if (width / 2) - 100 <= pos_x <= (width / 2) + 100 and pos_y >= (height - (height / 3)):
                        circle += 1
                        if click:
                            logger.debug('__read_circle_count: found Circle - click on: it')
                            await communicator.click(width / 2, ((int(height) - int(height / 4.5))) + pos_y)
                            await asyncio.sleep(2)

            logger.debug("__read_circle_count: Determined screenshot to have {} Circle.", circle)
            return circle
        else:
            logger.debug("__read_circle_count: Determined screenshot to have 0 Circle")
            return -1

    async def get_trash_click_positions(self, origin, filename, full_screen=False):
        if not await AsyncioOsUtil.isfile(filename):
            logger.error("get_trash_click_positions: {} does not exist", filename)
            return None
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(self.__process_executor_pool, trash_image_matching,
                                          origin, filename, full_screen)

    async def look_for_button(self, origin, filename, ratiomin, ratiomax, communicator, upper: bool = False):
        if not await AsyncioOsUtil.isfile(filename):
            logger.error("look_for_button: {} does not exist", filename)
            return False

        return await self.__internal_look_for_button(origin, filename, ratiomin, ratiomax, communicator, upper)

    async def __internal_look_for_button(self, origin, filename, ratiomin, ratiomax, communicator, upper) -> bool:
        logger.debug("lookForButton: Reading lines")
        min_distance_to_middle = None
        try:
            screenshot_read = await AsyncioCv2.imread(filename)
            gray = await AsyncioCv2.cvtColor(screenshot_read, cv2.COLOR_BGR2GRAY)
        except cv2.error:
            logger.error("Screenshot corrupted")
            return False

        if screenshot_read is None:
            logger.error("Screenshot corrupted")
            return False

        height, width, _ = screenshot_read.shape
        _widthold = float(width)
        logger.debug("lookForButton: Determined screenshot scale: {} x {}", height, width)

        # resize for better line quality
        height, width = gray.shape
        factor = width / _widthold

        gray = await AsyncioCv2.GaussianBlur(gray, (3, 3), 0)
        edges = await AsyncioCv2.Canny(gray, 50, 200, apertureSize=3)

        # checking for all possible button lines
        max_line_length = (width / ratiomin) + (width * 0.18)
        logger.debug("lookForButton: MaxLineLength: {}", max_line_length)
        min_line_length = (width / ratiomax) - (width * 0.02)
        logger.debug("lookForButton: MinLineLength: {}", min_line_length)

        kernel = np.ones((2, 2), np.uint8)
        # not async since the results were different to what they should've looked like - no idea as to why
        edges = cv2.morphologyEx(edges, cv2.MORPH_GRADIENT, kernel)

        num_lines = 0
        lines = cv2.HoughLinesP(edges, rho=1, theta=math.pi / 180, threshold=90, minLineLength=min_line_length,
                                maxLineGap=5)
        if lines is None:
            return False

        loop = asyncio.get_running_loop()
        with concurrent.futures.ThreadPoolExecutor() as pool:
            lines = await loop.run_in_executor(
                pool, self.__check_lines, lines, height)

        _last_y = 0
        for line in lines:
            line = [line]
            for x1, y1, x2, y2 in line:

                if y1 == y2 and max_line_length >= x2 - x1 >= min_line_length \
                        and y1 > height / 3 \
                        and width / 2 + 50 > (x2 - x1) / 2 + x1 > width / 2 - 50:

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
                    logger.debug("lookForButton: Found Buttonline Nr. {} - Line lenght: {}px Coords - X: {} {} "
                                 "Y: {} {}", num_lines, x2 - x1, x1, x2, y1, y1)

        if 1 < num_lines <= 6:
            # recalculate click area for real resolution
            click_x = int(((width - _x2) + ((_x2 - _x1) / 2)) /
                          round(factor, 2))
            click_y = int(click_y)
            logger.debug('lookForButton: found Button - click on it')
            await communicator.click(click_x, click_y)
            await asyncio.sleep(4)
            return True

        elif num_lines > 6:
            logger.debug('lookForButton: found to much Buttons :) - close it')
            await communicator.click(int(width - (width / 7.2)),
                                     int(height - (height / 12.19)))
            await asyncio.sleep(4)

            return True

        logger.debug('lookForButton: did not found any Button')
        return False

    # TODO: Should this be called in an executor?
    def __check_lines(self, lines, height):
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

    async def __check_raid_line(self, filename, identifier, communicator, left_side=False, clickinvers=False):
        logger.debug("__check_raid_line: Reading lines")
        if left_side:
            logger.debug("__check_raid_line: Check nearby open ")
        try:
            screenshot_read = await AsyncioCv2.imread(filename)
        except Exception:
            logger.error("Screenshot corrupted")
            return False
        if screenshot_read is None:
            logger.error("Screenshot corrupted")
            return False

        if await self.__read_circle_count(os.path.join('', filename), identifier, float(11), communicator,
                                          xcord=False,
                                          crop=True,
                                          click=False, canny=True) == -1:
            logger.debug("__check_raid_line: Not active")
            return False

        height, width, _ = screenshot_read.shape
        # TODO: Async?
        screenshot_read = screenshot_read[int(height / 2) - int(height / 3):int(height / 2) + int(height / 3),
                          int(0):int(width)]
        gray = await AsyncioCv2.cvtColor(screenshot_read, cv2.COLOR_BGR2GRAY)
        gray = await AsyncioCv2.GaussianBlur(gray, (5, 5), 0)
        logger.debug("__check_raid_line: Determined screenshot scale: {} x {}", height, width)
        edges = await AsyncioCv2.Canny(gray, 50, 150, apertureSize=3)
        max_line_length = width / 3.30 + width * 0.03
        logger.debug("__check_raid_line: MaxLineLength: {}", max_line_length)
        min_line_length = width / 6.35 - width * 0.03
        logger.debug("__check_raid_line: MinLineLength: {}", min_line_length)
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
                        logger.debug("__check_raid_line: Raid-tab is active - Line length: {}px "
                                     "Coords - x: {} {} Y: {} {}", x2 - x1, x1, x2, y1, y2)
                        return True
                else:
                    if y1 == y2 and (x2 - x1 <= max_line_length) and (
                            x2 - x1 >= min_line_length) and (
                            (x1 < width / 2 and x2 < width / 2) or (
                            x1 < width / 2 < x2)) and y1 < (
                            height / 2):
                        logger.debug("__check_raid_line: Nearby is active - but not Raid-Tab")
                        if clickinvers:
                            raidtab_x = int(width - (x2 - x1))
                            raidtab_y = int(
                                (int(height / 2) - int(height / 3) + y1) * 0.9)
                            logger.debug('__check_raid_line: open Raid-Tab')
                            await communicator.click(raidtab_x, raidtab_y)
                            await asyncio.sleep(3)
                        return True
        logger.debug("__check_raid_line: Not active")
        return False

    async def __check_close_present(self, filename, identifier, communicator, radiusratio=12, x_coord=True) -> bool:
        if not await AsyncioOsUtil.isfile(filename):
            logger.warning("__check_close_present: {} does not exist", filename)
            return False

        try:
            image = await AsyncioCv2.imread(filename)
            height, width, _ = image.shape
        except Exception as e:
            logger.error("Screenshot corrupted: {}", e)
            return False

        imwrite_status = await AsyncioCv2.imwrite(os.path.join(self.temp_dir_path,
                                                               str(identifier) + '_exitcircle.jpg'), image)
        if not imwrite_status:
            logger.error("Could not save file: {} - check permissions and path",
                         os.path.join(self.temp_dir_path, str(identifier) + '_exitcircle.jpg'))
            return False

        return await self.__read_circle_count(os.path.join(self.temp_dir_path, str(identifier) + '_exitcircle.jpg'),
                                              identifier,
                                              float(radiusratio), communicator, xcord=False, crop=True, click=True,
                                              canny=True) > 0

    async def check_close_except_nearby_button(self, filename, identifier, communicator, close_raid=False):
        if not await AsyncioOsUtil.isfile(filename):
            logger.error("check_close_except_nearby_button: {} does not exist", filename)
            return False
        return await self.__internal_check_close_except_nearby_button(filename, identifier, communicator, close_raid)

    # checks for X button on any screen... could kill raidscreen, handle properly
    async def __internal_check_close_except_nearby_button(self, filename, identifier, communicator,
                                                          close_raid=False):
        logger.debug("__internal_check_close_except_nearby_button: Checking close except nearby with: file {}",
                     filename)
        try:
            screenshot_read = await AsyncioCv2.imread(filename)
        except cv2.error:
            logger.error("Screenshot corrupted")
            logger.debug("__internal_check_close_except_nearby_button: Screenshot corrupted...")
            return False
        if screenshot_read is None:
            logger.error("__internal_check_close_except_nearby_button: Screenshot corrupted")
            return False

        if not close_raid:
            logger.debug("__internal_check_close_except_nearby_button: Raid is not to be closed...")
            if not await AsyncioOsUtil.isfile(filename) \
                    or await self.__check_raid_line(filename, identifier, communicator) \
                    or await self.__check_raid_line(filename, identifier, communicator, True):
                # file not found or raid tab present
                logger.debug("__internal_check_close_except_nearby_button: Not checking for close button (X). "
                             "Input wrong OR nearby window open")
                return False
        logger.debug("__internal_check_close_except_nearby_button: Checking for close button (X). Input wrong "
                     "OR nearby window open")

        if await self.__check_close_present(filename, identifier, communicator, 10, True):
            logger.debug("Found close button (X). Closing the window - Ratio: 10")
            return True
        if await self.__check_close_present(filename, identifier, communicator, 11, True):
            logger.debug("Found close button (X). Closing the window - Ratio: 11")
            return True
        elif await self.__check_close_present(filename, identifier, communicator, 12, True):
            logger.debug("Found close button (X). Closing the window - Ratio: 12")
            return True
        elif await self.__check_close_present(filename, identifier, communicator, 14, True):
            logger.debug("Found close button (X). Closing the window - Ratio: 14")
            return True
        elif await self.__check_close_present(filename, identifier, communicator, 13, True):
            logger.debug("Found close button (X). Closing the window - Ratio: 13")
            return True
        else:
            logger.debug("Could not find close button (X).")
            return False

    async def get_inventory_text(self, filename, identifier, x1, x2, y1, y2) -> Optional[str]:
        if not await AsyncioOsUtil.isfile(filename):
            logger.error("get_inventory_text: {} does not exist", filename)
            return None

        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(self.__process_executor_pool, get_inventory_text,
                                          self.temp_dir_path, filename, identifier, x1, x2, y1, y2)

    async def check_pogo_mainscreen(self, filename, identifier):
        if not await AsyncioOsUtil.isfile(filename):
            logger.error("check_pogo_mainscreen: {} does not exist", filename)
            return False
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(self.__process_executor_pool, check_pogo_mainscreen,
                                          filename, identifier)

    async def get_screen_text(self, screenpath: str, identifier) -> Optional[dict]:
        if screenpath is None:
            logger.error("get_screen_text: image does not exist")
            return None

        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(self.__process_executor_pool, get_screen_text,
                                          screenpath, identifier)

    async def most_frequent_colour(self, screenshot, identifier) -> Optional[List[int]]:
        if screenshot is None:
            logger.error("get_screen_text: image does not exist")
            return None
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(self.__process_executor_pool, most_frequent_colour_internal,
                                          screenshot, identifier)

    async def screendetection_get_type_by_screen_analysis(self, image,
                                                          identifier) -> Optional[Tuple[ScreenType,
                                                                                        Optional[
                                                                                            dict], int, int, int]]:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(self.__process_executor_pool, screendetection_get_type_internal,
                                          image, identifier)
