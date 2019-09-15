import datetime
import time
import os
import cv2
from flask import (render_template, request, redirect)

from db.dbWrapperBase import DbWrapperBase
from madmin.functions import (auth_required, generate_device_screenshot_path, getBasePath, nocache)
from utils.MappingManager import MappingManager
from utils.functions import (creation_date, generate_phones,
                             image_resize)

from utils.adb import ADBConnect
from utils.madGlobals import ScreenshotType


class control(object):
    def __init__(self, db_wrapper: DbWrapperBase, args, mapping_manager: MappingManager, websocket, logger, app):
        self._db: DbWrapperBase = db_wrapper
        self._args = args
        if self._args.madmin_time == "12":
            self._datetimeformat = '%Y-%m-%d %I:%M:%S %p'
        else:
            self._datetimeformat = '%Y-%m-%d %H:%M:%S'
        self._adb_connect = ADBConnect(self._args)

        self._mapping_manager: MappingManager = mapping_manager

        self._ws_server = websocket
        self._ws_connected_phones: list = []
        self._logger = logger
        self._app = app
        self.add_route()

    def add_route(self):
        routes = [
            ("/phonecontrol", self.get_phonescreens),
            ("/take_screenshot", self.take_screenshot),
            ("/click_screenshot", self.click_screenshot),
            ("/swipe_screenshot", self.swipe_screenshot),
            ("/quit_pogo", self.quit_pogo),
            ("/restart_phone", self.restart_phone),
            ("/clear_game_data", self.clear_game_data),
            ("/send_gps", self.send_gps),
            ("/send_text", self.send_text),
            ("/send_command", self.send_command)
        ]
        for route, view_func in routes:
            self._app.route(route)(view_func)

    @auth_required
    @nocache
    def get_phonescreens(self):
        if not os.path.exists(os.path.join(self._args.temp_path, "madmin")):
            os.makedirs(os.path.join(self._args.temp_path, "madmin"))

        screens_phone = []
        ws_connected_phones = []
        if self._ws_server is not None:
            phones = self._ws_server.get_reg_origins().copy()
        else:
            phones = []
        devicemappings = self._mapping_manager.get_all_devicemappings()

        # Sort devices by name.
        phones = sorted(phones)
        for phonename in phones:
            ws_connected_phones.append(phonename)
            add_text = ""
            adb_option = False
            adb = devicemappings.get(phonename, {}).get('adb', False)
            if adb is not None and self._adb_connect.check_adb_status(adb) is not None:
                self._ws_connected_phones.append(adb)
                adb_option = True
                add_text = '<b>ADB</b>'
            else:
                self._ws_connected_phones.append(adb)

            filename = generate_device_screenshot_path(phonename, devicemappings, self._args)
            if os.path.isfile(filename):
                screenshot_ending: str = ".jpg"
                image_resize(filename, os.path.join(
                    self._args.temp_path, "madmin"), width=250)
                screen = "screenshot/madmin/screenshot_" + str(phonename) + screenshot_ending
                screens_phone.append(
                    generate_phones(phonename, add_text, adb_option,
                                    screen, filename, self._datetimeformat, dummy=False)
                )
            else:
                screen = "static/dummy.png"
                screens_phone.append(generate_phones(
                    phonename, add_text, adb_option, screen, filename, self._datetimeformat, dummy=True))

        for phonename in self._adb_connect.return_adb_devices():
            if phonename.serial not in self._ws_connected_phones:
                devicemappings = self._mapping_manager.get_all_devicemappings()
                for pho in devicemappings:
                    if phonename.serial == devicemappings[pho].get('adb', False):
                        adb_option = True
                        add_text = '<b>ADB - no WS<img src="/static/warning.png" width="20px" ' \
                                   'alt="NO websocket connection!"></b>'
                        filename = generate_device_screenshot_path(pho, devicemappings, self._args)
                        if os.path.isfile(filename):
                            image_resize(filename, os.path.join(
                                self._args.temp_path, "madmin"), width=250)
                            screenshot_ending: str = ".jpg"
                            screen = "screenshot/madmin/screenshot_" + str(pho) + screenshot_ending
                            screens_phone.append(generate_phones(
                                pho, add_text, adb_option, screen, filename, self._datetimeformat, dummy=False)
                            )
                        else:
                            screen = "static/dummy.png"
                            screens_phone.append(
                                generate_phones(pho, add_text, adb_option, screen, filename, self._datetimeformat,
                                                dummy=True)
                            )

        return render_template('phonescreens.html', editform=screens_phone, header="Phonecontrol", title="Phonecontrol")

    @auth_required
    def take_screenshot(self, origin=None, adb=False):
        origin = request.args.get('origin')
        useadb = request.args.get('adb', False)
        self._logger.info('MADmin: Making screenshot ({})', str(origin))
        devicemappings = self._mapping_manager.get_all_devicemappings()

        adb = devicemappings.get(origin, {}).get('adb', False)

        if useadb == 'True' and self._adb_connect.make_screenshot(adb, origin, "jpg"):
            self._logger.info('MADMin: ADB screenshot successfully ({})', str(origin))
        else:

            screenshot_type: ScreenshotType = ScreenshotType.JPEG
            if devicemappings.get(origin, {}).get("screenshot_type", "jpeg") == "png":
                screenshot_type = ScreenshotType.PNG

            screenshot_quality: int = devicemappings.get(origin, {}).get("screenshot_quality", 80)

            temp_comm = self._ws_server.get_origin_communicator(origin)
            temp_comm.get_screenshot(generate_device_screenshot_path(origin, devicemappings, self._args),
                                     screenshot_quality, screenshot_type)

        filename = generate_device_screenshot_path(origin, devicemappings, self._args)
        image_resize(filename, os.path.join(self._args.temp_path, "madmin"), width=250)

        creationdate = datetime.datetime.fromtimestamp(
            creation_date(filename)).strftime(self._datetimeformat)

        return creationdate

    @auth_required
    def click_screenshot(self):
        origin = request.args.get('origin')
        click_x = request.args.get('clickx')
        click_y = request.args.get('clicky')
        useadb = request.args.get('adb')
        devicemappings = self._mapping_manager.get_all_devicemappings()

        filename = generate_device_screenshot_path(origin, devicemappings, self._args)
        img = cv2.imread(filename, 0)
        height, width = img.shape[:2]

        real_click_x = int(width / float(click_x))
        real_click_y = int(height / float(click_y))
        adb = devicemappings.get(origin, {}).get('adb', False)

        if useadb == 'True' and self._adb_connect.make_screenclick(adb, origin, real_click_x, real_click_y):
            self._logger.info('MADMin: ADB screenclick successfully ({})', str(origin))
        else:
            self._logger.info('MADMin WS Click x:{} y:{} ({})', str(
                real_click_x), str(real_click_y), str(origin))
            temp_comm = self._ws_server.get_origin_communicator(origin)
            temp_comm.click(int(real_click_x), int(real_click_y))

        time.sleep(2)
        return self.take_screenshot(origin, useadb)

    @auth_required
    def swipe_screenshot(self):
        origin = request.args.get('origin')
        click_x = request.args.get('clickx')
        click_y = request.args.get('clicky')
        click_xe = request.args.get('clickxe')
        click_ye = request.args.get('clickye')
        useadb = request.args.get('adb')

        devicemappings = self._mapping_manager.get_all_devicemappings()

        filename = generate_device_screenshot_path(origin, devicemappings, self._args)
        img = cv2.imread(filename, 0)
        height, width = img.shape[:2]

        real_click_x = int(width / float(click_x))
        real_click_y = int(height / float(click_y))
        real_click_xe = int(width / float(click_xe))
        real_click_ye = int(height / float(click_ye))
        adb = devicemappings.get(origin, {}).get('adb', False)

        if useadb == 'True' and self._adb_connect.make_screenswipe(adb, origin, real_click_x,
                                                                   real_click_y, real_click_xe, real_click_ye):
            self._logger.info('MADMin: ADB screenswipe successfully ({})', str(origin))
        else:
            self._logger.info('MADMin WS Swipe x:{} y:{} xe:{} ye:{} ({})', str(real_click_x), str(real_click_y),
                        str(real_click_xe), str(real_click_ye), str(origin))
            temp_comm = self._ws_server.get_origin_communicator(origin)
            temp_comm.touchandhold(int(real_click_x), int(
                real_click_y), int(real_click_xe), int(real_click_ye))

        time.sleep(2)
        return self.take_screenshot(origin, useadb)

    @auth_required
    def quit_pogo(self):
        origin = request.args.get('origin')
        useadb = request.args.get('adb')
        restart = request.args.get('restart')
        devicemappings = self._mapping_manager.get_all_devicemappings()

        adb = devicemappings.get(origin, {}).get('adb', False)
        self._logger.info('MADmin: Restart Pogo ({})', str(origin))
        if useadb == 'True' and self._adb_connect.send_shell_command(adb, origin, "am force-stop com.nianticlabs.pokemongo"):
            self._logger.info('MADMin: ADB shell force-stop game command successfully ({})', str(origin))
            if restart:
                time.sleep(1)
                started = self._adb_connect.send_shell_command(adb, origin, "am start com.nianticlabs.pokemongo")
                if started:
                    self._logger.info('MADMin: ADB shell start game command successfully ({})', str(origin))
                else:
                    self._logger.error('MADMin: ADB shell start game command failed ({})', str(origin))
        else:
            temp_comm = self._ws_server.get_origin_communicator(origin)
            if restart:
                self._logger.info('MADMin: trying to restart game on {}', str(origin))
                temp_comm.restartApp("com.nianticlabs.pokemongo")
                time.sleep(1)
            else:
                self._logger.info('MADMin: trying to stop game on {}', str(origin))
                temp_comm.stopApp("com.nianticlabs.pokemongo")

            self._logger.info('MADMin: WS command successfully ({})', str(origin))
        time.sleep(2)
        return self.take_screenshot(origin, useadb)

    @auth_required
    def restart_phone(self):
        origin = request.args.get('origin')
        useadb = request.args.get('adb')
        devicemappings = self._mapping_manager.get_all_devicemappings()

        adb = devicemappings.get(origin, {}).get('adb', False)
        self._logger.info('MADmin: Restart Phone ({})', str(origin))
        if (useadb == 'True' and
                self._adb_connect.send_shell_command(
                        adb, origin,"am broadcast -a android.intent.action.BOOT_COMPLETED")):
            self._logger.info('MADMin: ADB shell command successfully ({})', str(origin))
        else:
            temp_comm = self._ws_server.get_origin_communicator(origin)
            temp_comm.reboot()
        return redirect(getBasePath(request) + '/phonecontrol')

    @auth_required
    def clear_game_data(self):
        origin = request.args.get('origin')
        useadb = request.args.get('adb')
        devicemappings = self._mapping_manager.get_all_devicemappings()

        adb = devicemappings.get(origin, {}).get('adb', False)
        self._logger.info('MADmin: Clear game data for phone ({})', str(origin))
        if (useadb == 'True' and
                self._adb_connect.send_shell_command(
                        adb, origin, "pm clear com.nianticlabs.pokemongo")):
            self._logger.info('MADMin: ADB shell command successfully ({})', str(origin))
        else:
            temp_comm = self._ws_server.get_origin_communicator(origin)
            temp_comm.resetAppdata("com.nianticlabs.pokemongo")
        return redirect(getBasePath(request) + '/phonecontrol')


    @auth_required
    def send_gps(self):
        origin = request.args.get('origin')
        devicemappings = self._mapping_manager.get_all_devicemappings()

        useadb = request.args.get('adb')
        if useadb is None:
            useadb = devicemappings.get(origin, {}).get('adb', False)

        coords = request.args.get('coords').replace(' ', '').split(',')
        sleeptime = request.args.get('sleeptime', "0")
        if len(coords) < 2:
            return 'Wrong Format!'
        self._logger.info('MADmin: Set GPS Coords {}, {} - WS Mode only! ({})',
                    str(coords[0]), str(coords[1]), str(origin))
        try:
            temp_comm = self._ws_server.get_origin_communicator(origin)
            temp_comm.setLocation(coords[0], coords[1], 0)
            if int(sleeptime) > 0:
                self._logger.info("MADmin: Set additional sleeptime: {} ({})",
                            str(sleeptime), str(origin))
                self._ws_server.set_geofix_sleeptime_worker(origin, sleeptime)
        except Exception as e:
            self._logger.exception(
                'MADmin: Exception occurred while set gps coords: {}.', e)

        time.sleep(2)
        return self.take_screenshot(origin, useadb)

    @auth_required
    def send_text(self):
        origin = request.args.get('origin')
        useadb = request.args.get('adb')
        text = request.args.get('text')
        devicemappings = self._mapping_manager.get_all_devicemappings()

        adb = devicemappings.get(origin, {}).get('adb', False)
        if len(text) == 0:
            return 'Empty text'
        self._logger.info('MADmin: Send text ({})', str(origin))
        if useadb == 'True' and self._adb_connect.send_shell_command(adb, origin, 'input text "' + text + '"'):
            self._logger.info('MADMin: Send text successfully ({})', str(origin))
        else:
            temp_comm = self._ws_server.get_origin_communicator(origin)
            temp_comm.sendText(text)

        time.sleep(2)
        return self.take_screenshot(origin, useadb)

    @auth_required
    def send_command(self):
        origin = request.args.get('origin')
        useadb = request.args.get('adb')
        command = request.args.get('command')
        devicemappings = self._mapping_manager.get_all_devicemappings()

        adb = devicemappings.get(origin, {}).get('adb', False)
        self._logger.info('MADmin: Sending Command ({})', str(origin))
        if command == 'home':
            cmd = "input keyevent 3"
        elif command == 'back':
            cmd = "input keyevent 4"
        if useadb == 'True' and self._adb_connect.send_shell_command(adb, origin, cmd):
            self._logger.info('MADMin: ADB shell command successfully ({})', str(origin))
        else:
            temp_comm = self._ws_server.get_origin_communicator(origin)
            if command == 'home':
                temp_comm.homeButton()
            elif command == 'back':
                temp_comm.backButton()

        time.sleep(2)
        return self.take_screenshot(origin, useadb)
