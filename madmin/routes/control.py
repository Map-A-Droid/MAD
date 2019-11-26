import datetime
import time
import os
from PIL import Image
from flask import (render_template, request, redirect, flash, jsonify, url_for)
from werkzeug.utils import secure_filename

from db.DbWrapper import DbWrapper
from madmin.functions import (auth_required, generate_device_screenshot_path, nocache, allowed_file,
                              uploaded_files)
from utils.MappingManager import MappingManager
from utils.functions import (creation_date, generate_phones, image_resize)
from utils.logging import logger

from utils.adb import ADBConnect
from utils.madGlobals import ScreenshotType
from multiprocessing import  Queue
from threading import Thread
from queue import Empty
from utils.updater import jobType

class control(object):
    def __init__(self, db_wrapper: DbWrapper, args, mapping_manager: MappingManager, websocket, logger, app,
                 deviceUpdater):
        self._db: DbWrapper = db_wrapper
        self._args = args
        if self._args.madmin_time == "12":
            self._datetimeformat = '%Y-%m-%d %I:%M:%S %p'
        else:
            self._datetimeformat = '%Y-%m-%d %H:%M:%S'
        self._adb_connect = ADBConnect(self._args)
        self._device_updater = deviceUpdater
        self.research_trigger_queue = Queue()

        self._mapping_manager: MappingManager = mapping_manager

        self._ws_server = websocket
        self._ws_connected_phones: list = []
        self._logger = logger
        self._app = app
        self.add_route()

        self.trigger_thread = None
        self.trigger_thread = Thread(name='research_trigger', target=self.research_trigger)
        self.trigger_thread.daemon = True
        self.trigger_thread.start()

    def add_route(self):
        routes = [
            ("/devicecontrol", self.get_phonescreens),
            ("/take_screenshot", self.take_screenshot),
            ("/click_screenshot", self.click_screenshot),
            ("/swipe_screenshot", self.swipe_screenshot),
            ("/quit_pogo", self.quit_pogo),
            ("/restart_phone", self.restart_phone),
            ("/clear_game_data", self.clear_game_data),
            ("/send_gps", self.send_gps),
            ("/send_text", self.send_text),
            ("/upload", self.upload),
            ("/send_command", self.send_command),
            ("/get_uploaded_files", self.get_uploaded_files),
            ("/uploaded_files", self.uploaded_files),
            ("/delete_file", self.delete_file),
            ("/install_file", self.install_file),
            ("/get_install_log", self.get_install_log),
            ("/delete_log_entry", self.delete_log_entry),
            ("/install_status", self.install_status),
            ("/install_file_all_devices", self.install_file_all_devices),
            ("/restart_job", self.restart_job),
            ("/delete_log", self.delete_log),
            ("/get_all_workers", self.get_all_workers),
            ("/job_for_worker", self.job_for_worker),
            ("/reload_jobs", self.reload_jobs),
            ("/trigger_research_menu", self.trigger_research_menu),
            ("/flushlevel", self.flush)
        ]
        for route, view_func in routes:
            self._app.route(route, methods=['GET', 'POST'])(view_func)

    @logger.catch()
    def research_trigger(self):
        logger.info("Starting research trigger thread")
        while True:
            try:
                try:
                    origin = self.research_trigger_queue.get()
                except Empty:
                    time.sleep(2)
                    continue

                logger.info("Trigger research menu for device {}".format(str(origin)))
                self._ws_server.trigger_worker_check_research(origin)
                self.generate_screenshot(origin)
                time.sleep(3)

            except KeyboardInterrupt as e:
                logger.info("research_trigger received keyboard interrupt, stopping")
                if self.trigger_thread is not None:
                    self.trigger_thread.join()
                break

    @auth_required
    @nocache
    @logger.catch()
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

        return render_template('phonescreens.html', editform=screens_phone, header="Device control", title="Device control")

    @auth_required
    def take_screenshot(self, origin=None, adb=False):
        origin = request.args.get('origin')
        useadb = request.args.get('adb', False)
        self._logger.info('MADmin: Making screenshot ({})', str(origin))

        devicemappings = self._mapping_manager.get_all_devicemappings()
        adb = devicemappings.get(origin, {}).get('adb', False)
        filename = generate_device_screenshot_path(origin, devicemappings, self._args)

        if useadb == 'True' and self._adb_connect.make_screenshot(adb, origin, "jpg"):
            self._logger.info('MADMin: ADB screenshot successfully ({})', str(origin))
        else:
            self.generate_screenshot(origin)

        creationdate = datetime.datetime.fromtimestamp(
            creation_date(filename)).strftime(self._datetimeformat)

        return creationdate

    def generate_screenshot(self, origin):
        devicemappings = self._mapping_manager.get_all_devicemappings()
        screenshot_type: ScreenshotType = ScreenshotType.JPEG
        if devicemappings.get(origin, {}).get("screenshot_type", "jpeg") == "png":
            screenshot_type = ScreenshotType.PNG

        screenshot_quality: int = devicemappings.get(origin, {}).get("screenshot_quality", 80)

        temp_comm = self._ws_server.get_origin_communicator(origin)
        temp_comm.get_screenshot(generate_device_screenshot_path(origin, devicemappings, self._args),
                                 screenshot_quality, screenshot_type)

        filename = generate_device_screenshot_path(origin, devicemappings, self._args)
        image_resize(filename, os.path.join(self._args.temp_path, "madmin"), width=250)

        return

    @auth_required
    def click_screenshot(self):
        origin = request.args.get('origin')
        click_x = request.args.get('clickx')
        click_y = request.args.get('clicky')
        useadb = request.args.get('adb')
        devicemappings = self._mapping_manager.get_all_devicemappings()

        filename = generate_device_screenshot_path(origin, devicemappings, self._args)
        with Image.open(filename) as screenshot:
            width, height = screenshot.size

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
        with Image.open(filename) as screenshot:
            width, height = screenshot.size

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
        if useadb == 'True' and \
                self._adb_connect.send_shell_command(adb, origin, "am force-stop com.nianticlabs.pokemongo"):
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
        self._logger.info('MADmin: Restart device ({})', str(origin))
        if (useadb == 'True' and
                self._adb_connect.send_shell_command(
                        adb, origin,"am broadcast -a android.intent.action.BOOT_COMPLETED")):
            self._logger.info('MADMin: ADB shell command successfully ({})', str(origin))
        else:
            temp_comm = self._ws_server.get_origin_communicator(origin)
            temp_comm.reboot()
        return redirect(url_for('get_phonescreens'), code=302)

    @auth_required
    def clear_game_data(self):
        origin = request.args.get('origin')
        useadb = request.args.get('adb')
        devicemappings = self._mapping_manager.get_all_devicemappings()

        adb = devicemappings.get(origin, {}).get('adb', False)
        self._logger.info('MADmin: Clear game data for device ({})', str(origin))
        if (useadb == 'True' and
                self._adb_connect.send_shell_command(
                        adb, origin, "pm clear com.nianticlabs.pokemongo")):
            self._logger.info('MADMin: ADB shell command successfully ({})', str(origin))
        else:
            temp_comm = self._ws_server.get_origin_communicator(origin)
            temp_comm.resetAppdata("com.nianticlabs.pokemongo")
        return redirect(url_for('get_phonescreens'), code=302)


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
    def trigger_research_menu(self):
        origin = request.args.get('origin')
        try:
            self.research_trigger_queue.put(origin)
        except Exception as e:
            self._logger.exception(
                'MADmin: Exception occurred while trigger research menu: {}.', e)

        return redirect(url_for('get_phonescreens'), code=302)

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

    @auth_required
    @logger.catch
    def upload(self):
        if request.method == 'POST':
            # check if the post request has the file part
            if 'file' not in request.files:
                flash('No file part')
                return redirect(url_for('upload'), code=302)
            file = request.files['file']
            if file.filename == '':
                flash('No file selected for uploading')
                return redirect(url_for('upload'), code=302)
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                file.save(os.path.join(self._args.upload_path, filename))
                flash('File uploaded successfully')
                return redirect(url_for('uploaded_files'), code=302)
            else:
                flash('Allowed file type is apk only!')
                return redirect(url_for('upload'), code=302)

        return render_template('upload.html', header="File Upload", title="File Upload")

    @auth_required
    def get_uploaded_files(self):
        return jsonify(uploaded_files(self._datetimeformat, self._device_updater.return_commands()))

    @auth_required
    def uploaded_files(self):
        origin = request.args.get('origin', False)
        useadb = request.args.get('adb', False)
        return render_template('uploaded_files.html',
                               responsive=str(self._args.madmin_noresponsive).lower(),
                               title="Uploaded Files", origin=origin, adb=useadb)

    @auth_required
    def delete_file(self):
        filename = request.args.get('filename')
        if os.path.exists(os.path.join(self._args.upload_path, filename)):
            os.remove(os.path.join(self._args.upload_path, filename))
            flash('File deleted successfully')
        return redirect(url_for('uploaded_files'), code=302)

    @auth_required
    @logger.catch
    def install_file(self):

        jobname = request.args.get('jobname')
        origin = request.args.get('origin')
        useadb = request.args.get('adb', False)
        type_ = request.args.get('type', None)

        devicemappings = self._mapping_manager.get_all_devicemappings()
        adb = devicemappings.get(origin, {}).get('adb', False)

        if os.path.exists(os.path.join(self._args.upload_path, jobname)):
            if useadb == 'True':
                if self._adb_connect.push_file(adb, origin, os.path.join(self._args.upload_path, jobname)) and  \
                    self._adb_connect.send_shell_command(
                        adb, origin, "pm install -r /sdcard/Download/" + str(jobname)):
                    flash('File installed successfully')
                else:
                    flash('File could not be installed successfully :(')
            else:
                self._device_updater.preadd_job(origin=origin, job=jobname, id_=int(time.time()),
                                             type=type_)
                flash('File successfully queued --> See Job Status')

        elif type_ != jobType.INSTALLATION:
            self._device_updater.preadd_job(origin=origin, job=jobname, id_=int(time.time()),
                                         type=type_)
            flash('Job successfully queued --> See Job Status')

        return redirect(url_for('uploaded_files', origin=str(origin), adb=useadb), code=302)

    @auth_required
    def reload_jobs(self):
        logger.info("Reload existing jobs")
        self._device_updater.init_jobs()
        return redirect(url_for('uploaded_files'), code=302)


    @auth_required
    @logger.catch
    def get_install_log(self):
        withautojobs = request.args.get('withautojobs', False)
        return_log = []
        log = self._device_updater.get_log(withautojobs=withautojobs)
        for entry in log:
            if 'jobname' not in entry:
                entry['jobname'] = entry.get('file', 'Unknown Name')
            return_log.append(entry)

        return jsonify(return_log)

    @auth_required
    @logger.catch()
    def delete_log_entry(self):
        id_ = request.args.get('id')
        if self._device_updater.delete_log_id(id_):
            flash('Job deleted successfully')
        else:
            flash('Job could not be deleted successfully')
        return redirect(url_for('install_status'), code=302)

    @auth_required
    @logger.catch
    def install_status(self):
        withautojobs = request.args.get('withautojobs', False)
        return render_template('installation_status.html',
                               responsive=str(self._args.madmin_noresponsive).lower(),
                               title="Installation Status", withautojobs=withautojobs)

    @auth_required
    @logger.catch()
    def install_file_all_devices(self):
        jobname = request.args.get('jobname', None)
        type_ = request.args.get('type', None)
        if jobname is None or type_ is None:
            flash('No File or Type selected')
            return redirect(url_for('install_status'), code=302)

        devices = self._mapping_manager.get_all_devices()
        for device in devices:
            self._device_updater.preadd_job(origin=device, job=jobname, id_=int(time.time()),
                                            type=type_)
            time.sleep(1)

        flash('Job successfully queued')
        return redirect(url_for('install_status'), code=302)

    @logger.catch
    @auth_required
    def flush(self):
        origin = request.args.get("origin")
        logger.info('Removing visitation status for {}...', origin)
        self._db.flush_levelinfo(origin)
        return redirect(url_for('settings_devices'), code=302)

    @auth_required
    @logger.catch()
    def restart_job(self):
        id: int = request.args.get('id', None)
        if id is not None:
            self._device_updater.restart_job(id)
            flash('Job requeued')
            return redirect(url_for('install_status'), code=302)

        flash('unknown id - restart failed')
        return redirect(url_for('install_status'), code=302)

    @auth_required
    @logger.catch()
    def delete_log(self):
        onlysuccess = request.args.get('only_success', False)
        self._device_updater.delete_log(onlysuccess=onlysuccess)
        return redirect(url_for('install_status'), code=302)

    @auth_required
    def get_all_workers(self):
        devices = self._mapping_manager.get_all_devices()
        devicesreturn = []
        for device in devices:
            devicesreturn.append({'worker': device})

        return jsonify(devicesreturn)

    @auth_required
    def job_for_worker(self):
        jobname = request.args.get('jobname', None)
        type_ = request.args.get('type', None)
        devices = request.args.getlist('device[]')
        for device in devices:
            self._device_updater.preadd_job(origin=device, job=jobname, id_=int(time.time()),
                                            type=type_)
            time.sleep(1)

        flash('Job successfully queued')
        return redirect(url_for('install_status'), code=302)
