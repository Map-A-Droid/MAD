import asyncio
import os
import re
import time
import xml.etree.ElementTree as ET  # noqa: N817
from enum import Enum
from typing import Optional, Tuple

import numpy as np
from loguru import logger

from mapadroid.account_handler.AbstractAccountHandler import AbstractAccountHandler, BurnType
from mapadroid.db.model import SettingsPogoauth
from mapadroid.mapping_manager import MappingManager
from mapadroid.mapping_manager.MappingManagerDevicemappingKey import \
    MappingManagerDevicemappingKey
from mapadroid.ocr.screen_type import ScreenType
from mapadroid.utils.collections import ScreenCoordinates
from mapadroid.utils.madGlobals import ScreenshotType, application_args
from mapadroid.websocket.AbstractCommunicator import AbstractCommunicator
from mapadroid.worker.WorkerState import WorkerState


class LoginType(Enum):
    UNKNOWN = -1
    google = 1
    ptc = 2


class WordToScreenMatching(object):
    def __init__(self, communicator: AbstractCommunicator, worker_state: WorkerState,
                 mapping_mananger: MappingManager, account_handler: AbstractAccountHandler):
        # TODO: Somehow prevent call from elsewhere? Raise exception and only init in WordToScreenMatching.create?
        self._worker_state: WorkerState = worker_state
        self._mapping_manager: MappingManager = mapping_mananger
        self._account_handler: AbstractAccountHandler = account_handler
        self._ratio: float = 0.0

        self._screenshot_y_offset: int = 0
        self._nextscreen: ScreenType = ScreenType.UNDEFINED

        self._communicator: AbstractCommunicator = communicator
        logger.info("Starting Screendetector")
        self._width: int = 0
        self._height: int = 0

    @classmethod
    async def create(cls, communicator: AbstractCommunicator, worker_state: WorkerState,
                     mapping_mananger: MappingManager, account_handler: AbstractAccountHandler):
        self = WordToScreenMatching(communicator=communicator, worker_state=worker_state,
                                    mapping_mananger=mapping_mananger,
                                    account_handler=account_handler)
        self._accountindex = await self.get_devicesettings_value(MappingManagerDevicemappingKey.ACCOUNT_INDEX, 0)
        self._screenshot_y_offset = await self.get_devicesettings_value(
            MappingManagerDevicemappingKey.SCREENSHOT_Y_OFFSET, 0)
        return self

    # TODO: unused?
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

    async def __evaluate_topmost_app(self, topmost_app: str) -> Tuple[ScreenType, dict, int]:
        returntype: ScreenType = ScreenType.UNDEFINED
        global_dict: dict = {}
        diff = 1
        if "AccountPickerActivity" in topmost_app or 'SignInActivity' in topmost_app:
            return ScreenType.GGL, global_dict, diff
        elif "GrantPermissionsActivity" in topmost_app:
            return ScreenType.PERMISSION, global_dict, diff
        elif "GrantCredentialsWithAclNoTouchActivity" in topmost_app or "GrantCredentials" in topmost_app:
            return ScreenType.CREDENTIALS, global_dict, diff
        elif "ConsentActivity" in topmost_app:
            return ScreenType.CONSENT, global_dict, diff
        elif "/a.m" in topmost_app:
            logger.error("Likely found 'not responding' popup - reboot device (topmost app: {})", topmost_app)
            return ScreenType.NOTRESPONDING, global_dict, diff
        elif "com.nianticlabs.pokemongo" not in topmost_app:
            logger.warning("PoGo is not opened! Current topmost app: {}", topmost_app)
            return ScreenType.CLOSE, global_dict, diff
        elif self._nextscreen != ScreenType.UNDEFINED:
            # TODO: how can the nextscreen be known in the current? o.O
            return self._nextscreen, global_dict, diff
        elif not await self.get_devicesettings_value(MappingManagerDevicemappingKey.SCREENDETECTION, True):
            logger.info('Screen detection is disabled')
            return ScreenType.DISABLED, global_dict, diff
        else:
            result = await self._take_and_analyze_screenshot()
            if not result:
                logger.error("_check_windows: Failed getting/analyzing screenshot")
                return ScreenType.ERROR, global_dict, diff
            else:
                returntype, global_dict, diff = result
            if not global_dict:
                self._nextscreen = ScreenType.UNDEFINED
                logger.warning('Could not understand any text on screen - starting next round...')
                return ScreenType.ERROR, global_dict, diff

            self._ratio = self._height / self._width

            logger.debug("Screenratio: {}", self._ratio)

            if 'text' not in global_dict:
                logger.error('Error while text detection')
                return ScreenType.ERROR, global_dict, diff
            elif returntype == ScreenType.UNDEFINED and "com.nianticlabs.pokemongo" in topmost_app:
                return ScreenType.POGO, global_dict, diff

        return returntype, global_dict, diff

    async def __handle_login_screen(self, global_dict: dict, diff: int) -> None:
        temp_dict: dict = {}
        n_boxes = len(global_dict['text'])
        logger.debug("Selecting login with: {}", global_dict)
        if self._worker_state.active_account_last_set + 300 < time.time():
            logger.info("Detected login screen, fetching new account to use since last account was assigned more "
                        "than 5minutes ago")
            account_to_use: Optional[SettingsPogoauth] = await self._account_handler.get_account(
                self._worker_state.device_id,
                await self._mapping_manager.routemanager_get_purpose_of_device(self._worker_state.area_id),
                self._worker_state.current_location
            )
            if not account_to_use:
                logger.error("No account to use found, are there too few accounts in DB or did MAD screw up here?")
            else:
                self._worker_state.active_account = account_to_use
                self._worker_state.active_account_last_set = int(time.time())
        if not self._worker_state.active_account:
            logger.error("No account set for device.")
        for i in range(n_boxes):
            if 'Facebook' in (global_dict['text'][i]):
                temp_dict['Facebook'] = global_dict['top'][i] / diff
            if 'CLUB' in (global_dict['text'][i]):
                temp_dict['CLUB'] = global_dict['top'][i] / diff
            # french ...
            if 'DRESSEURS' in (global_dict['text'][i]):
                temp_dict['CLUB'] = global_dict['top'][i] / diff
            if 'Google' in (global_dict['text'][i]):
                temp_dict['Google'] = global_dict['top'][i] / diff

            if self._worker_state.active_account \
                    and self._worker_state.active_account.login_type == LoginType.ptc.value:
                self._nextscreen = ScreenType.PTC
                if 'CLUB' in (global_dict['text'][i]):
                    logger.info("ScreenType.LOGINSELECT (c) using PTC (logintype in Device Settings)")
                    await self._click_center_button(diff, global_dict, i)
                    await asyncio.sleep(5)
                    return

                # alternative select - calculate down from Facebook button
                elif 'Facebook' in temp_dict:
                    click_x = self._width / 2
                    click_y = (temp_dict['Facebook'] + 2 * self._height / 10.11)
                    logger.info("ScreenType.LOGINSELECT (f) using PTC (logintype in Device Settings)")
                    await self._communicator.click(int(click_x), int(click_y))
                    await asyncio.sleep(5)
                    return

                # alternative select - calculate down from Google button
                elif 'Google' in temp_dict:
                    click_x = self._width / 2
                    click_y = (temp_dict['Google'] + self._height / 10.11)
                    logger.info("ScreenType.LOGINSELECT (g) using PTC (logintype in Device Settings)")
                    await self._communicator.click(int(click_x), int(click_y))
                    await asyncio.sleep(5)
                    return

            else:
                self._nextscreen = ScreenType.UNDEFINED
                if 'Google' in (global_dict['text'][i]):
                    logger.info("ScreenType.LOGINSELECT (g) using Google Account (logintype in Device Settings)")
                    await self._click_center_button(diff, global_dict, i)
                    await asyncio.sleep(5)
                    return

                # alternative select
                elif 'Facebook' in temp_dict and 'CLUB' in temp_dict:
                    click_x = self._width / 2
                    click_y = (temp_dict['Facebook'] + ((temp_dict['CLUB'] - temp_dict['Facebook']) / 2))
                    logger.info("ScreenType.LOGINSELECT (fc) using Google Account (logintype in Device Settings)")
                    await self._communicator.click(int(click_x), int(click_y))
                    await asyncio.sleep(5)
                    return

                # alternative select
                elif 'Facebook' in temp_dict:
                    click_x = self._width / 2
                    click_y = (temp_dict['Facebook'] + self._height / 10.11)
                    logger.info("ScreenType.LOGINSELECT (f) using Google Account (logintype in Device Settings)")
                    await self._communicator.click(int(click_x), int(click_y))
                    await asyncio.sleep(5)
                    return

                # alternative select
                elif 'CLUB' in temp_dict:
                    click_x = self._width / 2
                    click_y = (temp_dict['CLUB'] - self._height / 10.11)
                    logger.info("ScreenType.LOGINSELECT (c) using Google Account (logintype in Device Settings)")
                    await self._communicator.click(int(click_x), int(click_y))
                    await asyncio.sleep(5)
                    return

    async def _click_center_button(self, diff, global_dict, i) -> None:
        (x, y, w, h) = (global_dict['left'][i], global_dict['top'][i],
                        global_dict['width'][i], global_dict['height'][i])
        logger.debug("Diff: {}", diff)
        click_x, click_y = (x + w / 2) / diff, (y + h / 2) / diff
        await self._communicator.click(click_x, click_y)

    async def __handle_screentype(self, screentype: ScreenType,
                                  global_dict: Optional[dict] = None, diff: int = -1,
                                  y_offset: int = 0) -> ScreenType:
        if screentype == ScreenType.UNDEFINED:
            logger.warning("Undefined screentype, abandon ship...")
        elif screentype == ScreenType.BIRTHDATE:
            await self.__handle_birthday_screen()
        elif screentype == ScreenType.RETURNING:
            await self.__handle_returning_player_or_wrong_credentials()
        elif screentype == ScreenType.LOGINSELECT:
            await self.__handle_login_screen(global_dict, diff)
        elif screentype == ScreenType.PTC:
            return await self.__handle_ptc_login()
        elif screentype == ScreenType.FAILURE:
            await self.__handle_failure_screen()
        elif screentype == ScreenType.RETRY:
            await self.__handle_retry_screen(diff, global_dict)
        elif screentype == ScreenType.WRONG:
            await self.__handle_returning_player_or_wrong_credentials()
            screentype = ScreenType.ERROR
        elif screentype == ScreenType.LOGINTIMEOUT:
            await self.__handle_login_timeout(diff, global_dict)
        elif screentype == ScreenType.GAMEDATA:
            self._nextscreen = ScreenType.UNDEFINED
        elif screentype == ScreenType.GGL:
            screentype = await self.__handle_google_login(screentype)
        elif screentype == ScreenType.PERMISSION:
            screentype = await self.__handle_permissions_screen(screentype)
        elif screentype == ScreenType.CREDENTIALS:
            screentype = await self.__handle_permissions_screen(screentype)
        elif screentype == ScreenType.MARKETING:
            await self.__handle_marketing_screen(diff, global_dict)
        elif screentype == ScreenType.CONSENT:
            screentype = await self.__handle_ggl_consent_screen()
        elif screentype == ScreenType.SN:
            self._nextscreen = ScreenType.UNDEFINED
        elif screentype == ScreenType.UPDATE:
            self._nextscreen = ScreenType.UNDEFINED
        elif screentype == ScreenType.NOGGL:
            self._nextscreen = ScreenType.UNDEFINED
        elif screentype == ScreenType.STRIKE:
            await self.__handle_strike_screen(diff, global_dict)
        elif screentype == ScreenType.SUSPENDED:
            self._nextscreen = ScreenType.UNDEFINED
            logger.warning('Account temporarily banned!')
            await self._account_handler.mark_burnt(self._worker_state.device_id,
                                                   BurnType.SUSPENDED)
            screentype = ScreenType.ERROR
        elif screentype == ScreenType.TERMINATED:
            self._nextscreen = ScreenType.UNDEFINED
            logger.error('Account permabanned!')
            await self._account_handler.mark_burnt(self._worker_state.device_id,
                                                   BurnType.BAN)
            screentype = ScreenType.ERROR
        # TODO auth: Detect maintenance screen
        elif screentype == ScreenType.POGO:
            screentype = await self.__check_pogo_screen_ban_or_loading(screentype, y_offset=y_offset)
        elif screentype == ScreenType.QUEST:
            logger.warning("Already on quest screen")
            # TODO: consider closing quest window?
            self._nextscreen = ScreenType.UNDEFINED
        elif screentype == ScreenType.GPS:
            self._nextscreen = ScreenType.UNDEFINED
            logger.warning("In game error detected")
        elif screentype == ScreenType.BLACK:
            logger.warning("Screen is black, sleeping a couple seconds for another check...")
        elif screentype == ScreenType.CLOSE:
            logger.debug("Detected pogo not open")
        elif screentype == ScreenType.DISABLED:
            logger.warning("Screendetection disabled")
        elif screentype == ScreenType.ERROR:
            logger.error("Error during screentype detection")

        return screentype

    async def __check_pogo_screen_ban_or_loading(self, screentype, y_offset: int = 0) -> ScreenType:
        backgroundcolor = await self._worker_state.pogo_windows.most_frequent_colour(await self.get_screenshot_path(),
                                                                                     self._worker_state.origin,
                                                                                     y_offset=y_offset)
        if backgroundcolor is not None and (
                backgroundcolor[0] == 0 and
                backgroundcolor[1] == 0 and
                backgroundcolor[2] == 0):
            # Background is black - Loading ...
            screentype = ScreenType.BLACK
        elif backgroundcolor is not None and (
                backgroundcolor[0] == 16 and
                backgroundcolor[1] == 24 and
                backgroundcolor[2] == 33):
            # Got a strike warning
            screentype = ScreenType.STRIKE
        return screentype

    async def __handle_strike_screen(self, diff, global_dict) -> None:
        self._nextscreen = ScreenType.UNDEFINED
        logger.warning('Got a black strike warning!')
        click_text = 'GOT IT,ALLES KLAR'
        n_boxes = len(global_dict['text'])
        for i in range(n_boxes):
            if any(elem.lower() in (global_dict['text'][i].lower()) for elem in click_text.split(",")):
                await self._click_center_button(diff, global_dict, i)
                await asyncio.sleep(2)

    async def __handle_marketing_screen(self, diff, global_dict) -> None:
        self._nextscreen = ScreenType.POGO
        click_text = 'ERLAUBEN,ALLOW,AUTORISER'
        n_boxes = len(global_dict['text'])
        for i in range(n_boxes):
            if any(elem.lower() in (global_dict['text'][i].lower()) for elem in click_text.split(",")):
                await self._click_center_button(diff, global_dict, i)
                await asyncio.sleep(2)

    async def __handle_permissions_screen(self, screentype) -> ScreenType:
        self._nextscreen = ScreenType.UNDEFINED
        if not await self.parse_permission(await self._communicator.uiautomator()):
            screentype = ScreenType.ERROR
        await asyncio.sleep(2)
        return screentype

    async def __handle_google_login(self, screentype) -> ScreenType:
        self._nextscreen = ScreenType.UNDEFINED
        if self._worker_state.active_account and self._worker_state.active_account.login_type == LoginType.ptc.value:
            logger.warning('Really dont know how i get there ... using first @ggl address ... :)')
            username = await self.get_devicesettings_value(MappingManagerDevicemappingKey.GGL_LOGIN_MAIL, '@gmail.com')
        elif self._worker_state.active_account:
            username = self._worker_state.active_account.username
        else:
            logger.error("Failed determining which google account to use")
            return ScreenType.ERROR
        if await self.parse_ggl(await self._communicator.uiautomator(), username):
            logger.info("Sleeping 50 seconds - please wait!")
            await asyncio.sleep(50)
        else:
            screentype = ScreenType.ERROR
        return screentype

    async def __handle_retry_screen(self, diff, global_dict) -> None:
        self._nextscreen = ScreenType.UNDEFINED
        click_text = 'DIFFERENT,AUTRE,AUTORISER,ANDERES,KONTO,ACCOUNT'
        await self.__click_center_button_text(click_text, diff, global_dict)

    async def __click_center_button_text(self, click_text, diff, global_dict):
        n_boxes = len(global_dict['text'])
        for i in range(n_boxes):
            if any(elem in (global_dict['text'][i]) for elem in click_text.split(",")):
                await self._click_center_button(diff, global_dict, i)
                await asyncio.sleep(2)

    async def __handle_ptc_login(self) -> ScreenType:
        self._nextscreen = ScreenType.UNDEFINED
        if not self._worker_state.active_account:
            logger.error('No PTC Username and Password is set')
            return ScreenType.ERROR
        if float(self._ratio) >= 2:
            username_y = self._height / 2.0 + self._screenshot_y_offset
            password_y = self._height / 1.6 + self._screenshot_y_offset
            button_y = self._height / 1.35 + self._screenshot_y_offset
        elif float(self._ratio) >= 1.7:
            username_y = self._height / 1.98 + self._screenshot_y_offset
            password_y = self._height / 1.51 + self._screenshot_y_offset
            button_y = self._height / 1.24 + self._screenshot_y_offset
        elif float(self._ratio) < 1.7:
            username_y = self._height / 1.98 + self._screenshot_y_offset
            password_y = self._height / 1.51 + self._screenshot_y_offset
            button_y = self._height / 1.24 + self._screenshot_y_offset
        else:
            logger.error("Unhandled ratio, unlikely to be the case. Do open a github issue")
            return ScreenType.ERROR
        # username
        await self._communicator.click(int(self._width / 2), int(username_y))
        await asyncio.sleep(.5)
        await self._communicator.enter_text(self._worker_state.active_account.username)
        await self._communicator.click(100, 100)
        await asyncio.sleep(2)
        # password
        await self._communicator.click(int(self._width / 2), int(password_y))
        await asyncio.sleep(.5)
        await self._communicator.enter_text(self._worker_state.active_account.password)
        await self._communicator.click(100, 100)
        await asyncio.sleep(2)
        # button
        await self._communicator.click(int(self._width / 2), int(button_y))
        logger.info("Sleeping 50 seconds - please wait!")
        await asyncio.sleep(50)
        return ScreenType.PTC

    async def __handle_failure_screen(self) -> None:
        await self.__handle_returning_player_or_wrong_credentials()

    async def __handle_ggl_consent_screen(self) -> ScreenType:
        if self._width == 0 and self._height == 0:
            logger.warning("Screen width and height are zero - try to get real values from new screenshot ...")
            # this updates self._width, self._height
            result = await self._take_and_analyze_screenshot()
            if not result:
                logger.error("Failed getting/analyzing screenshot")
                return ScreenType.ERROR
        if (self._width != 720 and self._height != 1280) and (self._width != 1080 and self._height != 1920) and (
                self._width != 1440 and self._height != 2560):
            logger.warning("The google consent screen can only be handled on 720x1280, 1080x1920 and 1440x2560 screens "
                           f"(width is {self._width}, height is {self._height})")
            return ScreenType.ERROR
        logger.info("Click accept button")
        if self._width == 720 and self._height == 1280:
            await self._communicator.touch_and_hold(int(360), int(1080), int(360), int(500))
            await self._communicator.click(480, 1080)
        if self._width == 1080 and self._height == 1920:
            await self._communicator.touch_and_hold(int(360), int(1800), int(360), int(400))
            await self._communicator.click(830, 1638)
        if self._width == 1440 and self._height == 2560:
            await self._communicator.touch_and_hold(int(360), int(2100), int(360), int(400))
            await self._communicator.click(976, 2180)
        await asyncio.sleep(10)
        return ScreenType.UNDEFINED

    async def __handle_returning_player_or_wrong_credentials(self) -> None:
        self._nextscreen = ScreenType.UNDEFINED
        screenshot_path = await self.get_screenshot_path()
        coordinates: Optional[ScreenCoordinates] = await self._worker_state.pogo_windows.look_for_button(
            screenshot_path,
            2.20, 3.01,
            upper=True)
        if coordinates:
            await self._communicator.click(coordinates.x, coordinates.y)
            await asyncio.sleep(2)

    async def __handle_birthday_screen(self) -> None:
        self._nextscreen = ScreenType.RETURNING
        click_x = int((self._width / 2) + (self._width / 4))
        click_y = int((self._height / 1.69) + self._screenshot_y_offset)
        await self._communicator.click(click_x, click_y)
        await self._communicator.touch_and_hold(click_x, click_y, click_x, int(click_y - (self._height / 2)), 200)
        await asyncio.sleep(1)
        await self._communicator.touch_and_hold(click_x, click_y, click_x, int(click_y - (self._height / 2)), 200)
        await asyncio.sleep(1)
        await self._communicator.click(click_x, click_y)
        await asyncio.sleep(1)
        click_x = int(self._width / 2)
        click_y = int(click_y + (self._height / 8.53))
        await self._communicator.click(click_x, click_y)
        await asyncio.sleep(1)

    async def detect_screentype(self, y_offset: int = 0) -> ScreenType:
        topmostapp = await self._communicator.topmost_app()
        if not topmostapp:
            logger.warning("Failed getting the topmost app!")
            return ScreenType.ERROR

        screentype, global_dict, diff = await self.__evaluate_topmost_app(topmost_app=topmostapp)
        logger.info("Processing Screen: {}", str(ScreenType(screentype)))
        return await self.__handle_screentype(screentype=screentype, global_dict=global_dict, diff=diff,
                                              y_offset=y_offset)

    async def check_quest(self, screenpath: str) -> ScreenType:
        if screenpath is None or len(screenpath) == 0:
            logger.error("Invalid screen path: {}", screenpath)
            return ScreenType.ERROR
        globaldict = await self._worker_state.pogo_windows.get_screen_text(screenpath, self._worker_state.origin)

        click_text = 'FIELD,SPECIAL,FELD,SPEZIAL,SPECIALES,TERRAIN'
        if not globaldict:
            # dict is empty
            return ScreenType.ERROR
        n_boxes = len(globaldict['text'])
        for i in range(n_boxes):
            if any(elem in (globaldict['text'][i]) for elem in click_text.split(",")):
                logger.info('Found research menu')
                await self._communicator.click(100, 100)
                return ScreenType.QUEST

        logger.info('Listening to Dr. blabla - please wait')

        await self._communicator.back_button()
        await asyncio.sleep(3)
        return ScreenType.UNDEFINED

    async def parse_permission(self, xml) -> bool:
        if xml is None:
            logger.warning('Something wrong with processing - getting None Type from Websocket...')
            return False
        click_text = ('ZULASSEN', 'ALLOW', 'AUTORISER', 'OK')
        try:
            parser = ET.XMLParser(encoding="utf-8")
            xmlroot = ET.fromstring(xml, parser=parser)
            bounds: str = ""
            for item in xmlroot.iter('node'):
                if str(item.attrib['text']).upper() in click_text:
                    logger.debug("Found text {}", item.attrib['text'])
                    bounds = item.attrib['bounds']
                    logger.debug("Bounds {}", item.attrib['bounds'])

                    match = re.search(r'^\[(\d+),(\d+)\]\[(\d+),(\d+)\]$', bounds)

                    click_x = int(match.group(1)) + ((int(match.group(3)) - int(match.group(1))) / 2)
                    click_y = int(match.group(2)) + ((int(match.group(4)) - int(match.group(2))) / 2)
                    await self._communicator.click(int(click_x), int(click_y))
                    await asyncio.sleep(2)
                    return True
        except Exception as e:
            logger.error('Something wrong while parsing xml: {}', e)
            logger.exception(e)
            return False

        await asyncio.sleep(2)
        logger.warning('Could not find any button...')
        return False

    async def parse_ggl(self, xml, mail: Optional[str]) -> bool:
        if xml is None:
            logger.warning('Something wrong with processing - getting None Type from Websocket...')
            return False
        try:
            parser = ET.XMLParser(encoding="utf-8")
            xmlroot = ET.fromstring(xml, parser=parser)
            for item in xmlroot.iter('node'):
                if (mail and mail.lower() in str(item.attrib['text']).lower()
                        or not mail and (item.attrib["resource-id"] == "com.google.android.gms:id/account_name"
                                         or "@" in str(item.attrib['text']))):
                    logger.info("Found mail {}", self.censor_account(str(item.attrib['text'])))
                    bounds = item.attrib['bounds']
                    logger.debug("Bounds {}", item.attrib['bounds'])
                    match = re.search(r'^\[(\d+),(\d+)\]\[(\d+),(\d+)\]$', bounds)
                    click_x = int(match.group(1)) + ((int(match.group(3)) - int(match.group(1))) / 2)
                    click_y = int(match.group(2)) + ((int(match.group(4)) - int(match.group(2))) / 2)
                    await self._communicator.click(int(click_x), int(click_y))
                    await asyncio.sleep(5)
                    return True
        except Exception as e:
            logger.error('Something wrong while parsing xml: {}', e)
            logger.exception(e)
            return False

        await asyncio.sleep(2)
        logger.warning('Dont find any mailaddress...')
        return False

    async def set_devicesettings_value(self, key: MappingManagerDevicemappingKey, value) -> None:
        await self._mapping_manager.set_devicesetting_value_of(self._worker_state.origin, key, value)

    async def get_devicesettings_value(self, key: MappingManagerDevicemappingKey, default_value: object = None):
        logger.debug2("Fetching devicemappings")
        try:
            value = await self._mapping_manager.get_devicesetting_value_of_device(self._worker_state.origin, key)
        except (EOFError, FileNotFoundError) as e:
            logger.warning("Failed fetching devicemappings in worker with description: {}. Stopping worker", e)
            return None
        return value if value is not None else default_value

    def censor_account(self, emailaddress, is_ptc=False):
        # PTC account
        if is_ptc:
            return (emailaddress[0:2] + "***" + emailaddress[-2:])
        # GGL - make sure we have @ there.
        # If not it could be wrong match, so returning original
        if '@' in emailaddress:
            user, domain = emailaddress.split("@", 1)
            # long local-part, censor middle part only
            if len(user) > 6:
                return (user[0:2] + "***" + user[-2:] + "@" + domain)
            # domain only, just return
            elif len(user) == 0:
                return (emailaddress)
            # local-part is short, asterix for each char
            else:
                return ("*" * len(user) + "@" + domain)
        return emailaddress

    async def get_screenshot_path(self, fileaddon: bool = False) -> str:
        screenshot_ending: str = ".jpg"
        addon: str = ""
        if await self.get_devicesettings_value(MappingManagerDevicemappingKey.SCREENSHOT_TYPE, "jpeg") == "png":
            screenshot_ending = ".png"

        if fileaddon:
            addon: str = "_" + str(time.time())

        screenshot_filename = "screenshot_{}{}{}".format(str(self._worker_state.origin), str(addon), screenshot_ending)

        if fileaddon:
            logger.info("Creating debugscreen: {}", screenshot_filename)

        return os.path.join(
            application_args.temp_path, screenshot_filename)

    async def _take_screenshot(self, delay_after=0.0, delay_before=0.0, errorscreen: bool = False):
        logger.debug("Taking screenshot...")
        await asyncio.sleep(delay_before)

        # TODO: area settings for jpg/png and quality?
        screenshot_type: ScreenshotType = ScreenshotType.JPEG
        if await self.get_devicesettings_value(MappingManagerDevicemappingKey.SCREENSHOT_TYPE, "jpeg") == "png":
            screenshot_type = ScreenshotType.PNG

        screenshot_quality: int = 80

        take_screenshot = await self._communicator.get_screenshot(await self.get_screenshot_path(fileaddon=errorscreen),
                                                                  screenshot_quality, screenshot_type)

        if not take_screenshot:
            logger.error("takeScreenshot: Failed retrieving screenshot")
            logger.debug("Failed retrieving screenshot")
            return False
        else:
            logger.debug("Success retrieving screenshot")
            self._lastScreenshotTaken = time.time()
            await asyncio.sleep(delay_after)
            return True

    async def __handle_login_timeout(self, diff, global_dict) -> None:
        self._nextscreen = ScreenType.UNDEFINED
        click_text = 'SIGNOUT,SIGN,ABMELDEN,_DECONNECTER'
        await self.__click_center_button_text(click_text, diff, global_dict)

    async def _take_and_analyze_screenshot(self, delay_after=0.0, delay_before=0.0, errorscreen: bool = False) -> \
            Optional[Tuple[ScreenType,
            Optional[
                dict], int]]:
        if not await self._take_screenshot(delay_before=await self.get_devicesettings_value(
                MappingManagerDevicemappingKey.POST_SCREENSHOT_DELAY, 1),
                                           delay_after=2):
            logger.error("Failed getting screenshot")
            return None

        screenpath = await self.get_screenshot_path()

        result: Optional[Tuple[ScreenType,
        Optional[
            dict], int, int, int]] = await self._worker_state.pogo_windows \
            .screendetection_get_type_by_screen_analysis(screenpath, self._worker_state.origin)
        if result is None:
            logger.error("Failed analyzing screen")
            return None
        else:
            returntype, global_dict, self._width, self._height, diff = result
            return returntype, global_dict, diff
