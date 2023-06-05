from __future__ import annotations

import asyncio
import concurrent.futures
import math
import multiprocessing
import os
import os.path
from concurrent.futures.process import BrokenProcessPool
from functools import wraps
from typing import Any, List, Optional, Tuple

import cv2
import numpy as np
from loguru import logger

from mapadroid.ocr.screen_type import ScreenType
from mapadroid.ocr.utils import (check_pogo_mainscreen, get_screen_text,
                                 most_frequent_colour_internal,
                                 screendetection_get_type_internal)
from mapadroid.utils.AsyncioCv2 import AsyncioCv2
from mapadroid.utils.AsyncioOsUtil import AsyncioOsUtil
from mapadroid.utils.collections import ScreenCoordinates


def check_process_pool(func) -> Any:
    @wraps(func)
    async def decorated(self: PogoWindows, *args, **kwargs):
        try:
            return await func(self, *args, **kwargs)
        except BrokenProcessPool as e:
            logger.warning("Broken process pool exception was raised ('{}'), trying to recreate the pool.", e)
            await self.shutdown()
            self.__process_executor_pool = concurrent.futures.ProcessPoolExecutor(
                self._thread_count, mp_context=multiprocessing.get_context('spawn'))
            return await func(self, *args, **kwargs)

    return decorated


class PogoWindows:
    def __init__(self, temp_dir_path, thread_count: int):
        self._thread_count: int = thread_count
        # TODO: move to init? This will block if called in asyncio loop
        if not os.path.exists(temp_dir_path):
            os.makedirs(temp_dir_path)
            logger.info('PogoWindows: Temp directory created')
        self.temp_dir_path = temp_dir_path
        self.__process_executor_pool: concurrent.futures.ProcessPoolExecutor = concurrent.futures.ProcessPoolExecutor(
            thread_count, mp_context=multiprocessing.get_context('spawn'))

    async def shutdown(self):
        self.__process_executor_pool.shutdown()

    @check_process_pool
    async def __read_circles(self, filename, ratio, xcord=False, crop=False,
                             canny=False, secondratio=False) -> List[ScreenCoordinates]:
        logger.debug2("__read_circles: Reading circles")
        circles_found: List[ScreenCoordinates] = []
        try:
            screenshot_read = await AsyncioCv2.imread(filename, executor=self.__process_executor_pool)
        except Exception:
            logger.error("Screenshot corrupted")
            return circles_found

        if screenshot_read is None:
            logger.error("Screenshot corrupted")
            return circles_found

        height, width, _ = screenshot_read.shape

        if crop:
            screenshot_read = screenshot_read[int(height) - int(int(height / 4)):int(height),
                              int(int(width) / 2) - int(int(width) / 8):int(int(width) / 2) + int(
                                  int(width) / 8)]

        logger.debug("__read_circles: Determined screenshot scale: {} x {}", height, width)
        gray = await AsyncioCv2.cvtColor(screenshot_read, cv2.COLOR_BGR2GRAY, executor=self.__process_executor_pool)
        # detect circles in the image

        if not secondratio:
            radius_min = int((width / float(ratio) - 3) / 2)
            radius_max = int((width / float(ratio) + 3) / 2)
        else:
            radius_min = int((width / float(ratio) - 3) / 2)
            radius_max = int((width / float(secondratio) + 3) / 2)
        if canny:
            gaussian = await AsyncioCv2.GaussianBlur(gray, (3, 3), 0, executor=self.__process_executor_pool)
            del gray
            gray = await AsyncioCv2.Canny(gaussian, 100, 50, apertureSize=3, executor=self.__process_executor_pool)

        logger.debug("__read_circles: Detect radius of circle: Min {} / Max {}", radius_min, radius_max)
        circles = await AsyncioCv2.HoughCircles(gray, cv2.HOUGH_GRADIENT, 1, width / 8, param1=100, param2=15,
                                                minRadius=radius_min,
                                                maxRadius=radius_max, executor=self.__process_executor_pool)
        # ensure at least some circles were found
        if circles is not None:
            # convert the (x, y) coordinates and radius of the circles to integers
            circles_first_col = np.round(circles[0, :]).astype("int")
            del circles
            # loop over the (x, y) coordinates and radius of the circles
            for (pos_x, pos_y, _) in circles_first_col:
                if not xcord:
                    circles_found.append(ScreenCoordinates(width / 2, (int(height) - int(height / 4.5)) + pos_y))
                else:
                    if (width / 2) - 100 <= pos_x <= (width / 2) + 100 and pos_y >= (height - (height / 3)):
                        circles_found.append(ScreenCoordinates(width / 2, (int(height) - int(height / 4.5)) + pos_y))
            del circles_first_col
            logger.debug("__read_circles: Determined screenshot to have {} Circle.", len(circles_found))
            return circles_found
        else:
            logger.debug("__read_circles: Determined screenshot to have 0 Circle")
            return circles_found

    async def look_for_button(self, filename, ratiomin, ratiomax,
                              upper: bool = False) -> Optional[ScreenCoordinates]:
        if not await AsyncioOsUtil.isfile(filename):
            logger.error("look_for_button: {} does not exist", filename)
            return None

        return await self.__internal_look_for_button(filename, ratiomin, ratiomax, upper)

    @check_process_pool
    async def __internal_look_for_button(self, filename, ratiomin, ratiomax,
                                         upper) -> Optional[ScreenCoordinates]:
        logger.debug("lookForButton: Reading lines")
        min_distance_to_middle = None
        screenshot_read = None
        try:
            screenshot_read = await AsyncioCv2.imread(filename, executor=self.__process_executor_pool)
            gray = await AsyncioCv2.cvtColor(screenshot_read, cv2.COLOR_BGR2GRAY, executor=self.__process_executor_pool)
        except cv2.error:
            if screenshot_read is not None:
                del screenshot_read
            logger.error("Screenshot corrupted")
            return None

        if screenshot_read is None:
            logger.error("Screenshot corrupted")
            return None

        height, width, _ = screenshot_read.shape
        _widthold = float(width)
        logger.debug("lookForButton: Determined screenshot scale: {} x {}", height, width)

        # resize for better line quality
        height, width = gray.shape
        factor = width / _widthold

        gaussian = await AsyncioCv2.GaussianBlur(gray, (3, 3), 0, executor=self.__process_executor_pool)
        del gray
        edges = await AsyncioCv2.Canny(gaussian, 50, 200, apertureSize=3, executor=self.__process_executor_pool)
        del gaussian

        # checking for all possible button lines
        max_line_length = (width / ratiomin) + (width * 0.18)
        logger.debug("lookForButton: MaxLineLength: {}", max_line_length)
        min_line_length = (width / ratiomax) - (width * 0.02)
        logger.debug("lookForButton: MinLineLength: {}", min_line_length)

        kernel = np.ones((2, 2), np.uint8)
        # not async since the results were different to what they should've looked like - no idea as to why
        gradient_of_edges_found = cv2.morphologyEx(edges, cv2.MORPH_GRADIENT, kernel)
        del edges

        num_lines = 0
        lines = cv2.HoughLinesP(gradient_of_edges_found, rho=1, theta=math.pi / 180, threshold=90,
                                minLineLength=min_line_length, maxLineGap=5)
        del gradient_of_edges_found
        if lines is None:
            return None

        loop = asyncio.get_running_loop()
        with concurrent.futures.ThreadPoolExecutor() as pool:
            lines_processed = await loop.run_in_executor(
                pool, self.__check_lines, lines, height)
        del lines
        _last_y = _x1 = _x2 = click_y = 0
        for line in lines_processed:
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
        del lines_processed
        if 1 < num_lines <= 6:
            # recalculate click area for real resolution
            click_x = int(((width - _x2) + ((_x2 - _x1) / 2)) /
                          round(factor, 2))
            click_y = int(click_y)
            logger.debug('lookForButton: found Button')
            return ScreenCoordinates(click_x, click_y)

        elif num_lines > 6:
            logger.debug('lookForButton: found too many Buttons :) - assuming X coords to close present')
            return ScreenCoordinates(int(width - (width / 7.2)),
                                     int(height - (height / 12.19)))

        logger.debug('lookForButton: did not found any Button')
        return None

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

    @check_process_pool
    async def __check_raid_line(self, filename, left_side=False) -> Optional[ScreenCoordinates]:
        logger.debug("__check_raid_line: Reading lines")
        if left_side:
            logger.debug("__check_raid_line: Check nearby open ")
        try:
            screenshot_read = await AsyncioCv2.imread(filename, executor=self.__process_executor_pool)
        except Exception:
            logger.error("Screenshot corrupted")
            return None
        if screenshot_read is None:
            logger.error("Screenshot corrupted")
            return None

        if len(await self.__read_circles(os.path.join('', filename), float(11),
                                         xcord=False,
                                         crop=True,
                                         canny=True)) == 0:
            logger.debug("__check_raid_line: Not active")
            return None

        height, width, _ = screenshot_read.shape
        # TODO: Async?
        screenshot_partial = screenshot_read[int(height / 2) - int(height / 3):int(height / 2) + int(height / 3),
                             int(0):int(width)]
        del screenshot_read
        gray = await AsyncioCv2.cvtColor(screenshot_partial, cv2.COLOR_BGR2GRAY, executor=self.__process_executor_pool)
        del screenshot_partial
        gaussian = await AsyncioCv2.GaussianBlur(gray, (5, 5), 0, executor=self.__process_executor_pool)
        del gray
        logger.debug("__check_raid_line: Determined screenshot scale: {} x {}", height, width)
        edges = await AsyncioCv2.Canny(gaussian, 50, 150, apertureSize=3, executor=self.__process_executor_pool)
        del gaussian
        max_line_length = width / 3.30 + width * 0.03
        logger.debug("__check_raid_line: MaxLineLength: {}", max_line_length)
        min_line_length = width / 6.35 - width * 0.03
        logger.debug("__check_raid_line: MinLineLength: {}", min_line_length)
        lines = cv2.HoughLinesP(edges, rho=1, theta=math.pi / 180, threshold=70, minLineLength=min_line_length,
                                maxLineGap=2)
        del edges
        if lines is None:
            return None
        try:
            for line in lines:
                for x1, y1, x2, y2 in line:
                    if not left_side:
                        if y1 == y2 and (x2 - x1 <= max_line_length) and (
                                x2 - x1 >= min_line_length) and x1 > width / 2 and x2 > width / 2 and y1 < (
                                height / 2):
                            logger.debug("__check_raid_line: Raid-tab is active - Line length: {}px "
                                         "Coords - x: {} {} Y: {} {}", x2 - x1, x1, x2, y1, y2)
                            return ScreenCoordinates(0, 0)
                    else:
                        if y1 == y2 and (x2 - x1 <= max_line_length) and (
                                x2 - x1 >= min_line_length) and (
                                (x1 < width / 2 and x2 < width / 2) or (
                                x1 < width / 2 < x2)) and y1 < (
                                height / 2):
                            logger.debug("__check_raid_line: Nearby is active - but not Raid-Tab")
                            raidtab_x = int(width - (x2 - x1))
                            raidtab_y = int(
                                (int(height / 2) - int(height / 3) + y1) * 0.9)
                            return ScreenCoordinates(raidtab_x, raidtab_y)
        finally:
            del lines
        logger.debug("__check_raid_line: Not active")
        return None

    async def __check_close_present(self, filename, identifier, radiusratio=12, x_coord=True) -> List[
        ScreenCoordinates]:
        if not await AsyncioOsUtil.isfile(filename):
            logger.warning("__check_close_present: {} does not exist", filename)
            return []

        try:
            image = await AsyncioCv2.imread(filename, executor=self.__process_executor_pool)
            height, width, _ = image.shape
        except Exception as e:
            logger.error("Screenshot corrupted: {}", e)
            return []
        tmp_file_path = os.path.join(self.temp_dir_path,
                                     str(identifier) + '_exitcircle.jpg')
        imwrite_status = await AsyncioCv2.imwrite(tmp_file_path, image, executor=self.__process_executor_pool)
        if not imwrite_status:
            logger.error("Could not save file: {} - check permissions and path",
                         tmp_file_path)
            return []

        return await self.__read_circles(tmp_file_path,
                                         float(radiusratio), xcord=False, crop=True,
                                         canny=True)

    @check_process_pool
    async def check_close_except_nearby_button(self, filename, identifier, close_raid=False) -> List[ScreenCoordinates]:
        if not await AsyncioOsUtil.isfile(filename):
            logger.error("check_close_except_nearby_button: {} does not exist", filename)
            return []
        return await self.__internal_check_close_except_nearby_button(filename, identifier, close_raid)

    # checks for X button on any screen... could kill raidscreen, handle properly
    async def __internal_check_close_except_nearby_button(self, filename, identifier,
                                                          close_raid=False) -> List[ScreenCoordinates]:
        logger.debug("__internal_check_close_except_nearby_button: Checking close except nearby with: file {}",
                     filename)
        if not filename or not await AsyncioOsUtil.isfile(filename):
            logger.error("Screenshot not available")
            return []
        try:
            screenshot_read = await AsyncioCv2.imread(filename, executor=self.__process_executor_pool)
        except cv2.error:
            logger.error("Screenshot corrupted")
            logger.debug("__internal_check_close_except_nearby_button: Screenshot corrupted...")
            return []
        if screenshot_read is None:
            logger.error("__internal_check_close_except_nearby_button: Screenshot corrupted")
            return []
        else:
            del screenshot_read

        if not close_raid:
            logger.debug("__internal_check_close_except_nearby_button: Raid is not to be closed...")
            if await self.__check_raid_line(filename) \
                    or await self.__check_raid_line(filename, left_side=True):
                # file not found or raid tab present
                logger.debug("__internal_check_close_except_nearby_button: Not checking for close button (X). "
                             "Nearby or raid tab open but not to be closed.")
                return []
        logger.debug("__internal_check_close_except_nearby_button: Checking for close button (X).")

        ratio_to_use: int = 10
        coordinates_of_close_found: List[ScreenCoordinates] = []
        while not coordinates_of_close_found and ratio_to_use < 15:
            coordinates_of_close_found = await self.__check_close_present(filename, identifier, 10, True)
            if not coordinates_of_close_found:
                ratio_to_use += 1
            else:
                logger.debug("Found close button (X). Ratio: {}", ratio_to_use)
                return coordinates_of_close_found
        return []

    @check_process_pool
    async def check_pogo_mainscreen(self, filename, identifier) -> bool:
        if not await AsyncioOsUtil.isfile(filename):
            logger.error("check_pogo_mainscreen: {} does not exist", filename)
            return False
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(self.__process_executor_pool, check_pogo_mainscreen,
                                          filename, identifier)

    @check_process_pool
    async def get_screen_text(self, screenpath: str, identifier) -> Optional[dict]:
        if screenpath is None:
            logger.error("get_screen_text: image does not exist")
            return None

        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(self.__process_executor_pool, get_screen_text,
                                          screenpath, identifier)

    @check_process_pool
    async def most_frequent_colour(self, screenshot, identifier, y_offset: int = 0) -> Optional[List[int]]:
        if screenshot is None:
            logger.error("get_screen_text: image does not exist")
            return None
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(self.__process_executor_pool, most_frequent_colour_internal,
                                          screenshot, identifier, y_offset)

    @check_process_pool
    async def screendetection_get_type_by_screen_analysis(self, image,
                                                          identifier) -> Optional[Tuple[ScreenType,
                                                                                        Optional[
                                                                                            dict], int, int, int]]:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(self.__process_executor_pool, screendetection_get_type_internal,
                                          image, identifier)
