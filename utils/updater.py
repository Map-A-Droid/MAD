import json
import os
import glob
import time
from datetime import datetime, timedelta
from enum import Enum
from multiprocessing import  Queue
from threading import  RLock, Thread
from utils.logging import logger

class jobType(Enum):
    INSTALLATION = 0
    REBOOT = 1
    RESTART = 2
    STOP = 3
    PASSTHROUGH = 4
    START = 5
    CHAIN = 99

class deviceUpdater(object):
    def __init__(self, websocket, args):
        self._websocket = websocket
        self._update_queue = Queue()
        self._update_mutex = RLock()
        self._log = {}
        self._args = args
        self._commands: dict = {}
        self._globaljoblog: dict = {}
        self._current_job_id: int = None
        if os.path.exists('update_log.json'):
            with open('update_log.json') as logfile:
                self._log = json.load(logfile)

        self.init_jobs()
        self.kill_old_jobs()

        t_updater = Thread(name='apk_updater', target=self.process_update_queue)
        t_updater.daemon = False
        t_updater.start()

    def init_jobs(self):
        self._commands = {}
        if os.path.exists('commands.json'):
            with open('commands.json') as cmdfile:
                self._commands = json.loads(cmdfile.read())

        # load personal commands

        for file in glob.glob(os.path.join("personal_commands", "*.json")):
            try:
                with open(file) as personal_command:
                    peronal_cmd = json.loads(personal_command.read())
                for command in peronal_cmd:
                    if command in self._commands:
                         logger.error("Command {} already exist - skipping".format(str(command)))
                    else:
                        logger.info('Loading personal command: {}'.format(command))
                        self._commands[command] = peronal_cmd[command]
            except Exception as e:
                logger.error('Cannot add job {} - Reason: {}'.format(str(file), str(e)))

    def return_commands(self):
        return self._commands

    @logger.catch()
    def restart_job(self, id_: int):
        if (id_) in self._log:
            origin = self._log[id_]['origin']
            file_ = self._log[id_]['file']
            jobtype = self._log[id_]['jobtype']
            globalid = self._log[id_]['globalid']

            if globalid not in self._globaljoblog:
                self._globaljoblog[globalid] = {}
                self._globaljoblog[globalid]['laststatus'] = None
                self._globaljoblog[globalid]['lastjobend'] = None

            self.add_job(globalid=globalid, origin=origin, file=file_, id_=id_, type=jobtype, status='requeued')

        return True

    def kill_old_jobs(self):
        logger.info("Checking for outdated jobs")
        for job in self._log:
            if self._log[job]['status'] in ('pending', 'starting', 'processing', 'not connected', 'future'):
                logger.debug("Cancel job {} - it is outdated".format(str(job)))
                self._log[job]['status'] = 'canceled'
                self.update_status_log()

    @logger.catch()
    def process_update_queue(self):
        logger.info("Starting Device Job processor")
        while True:
            try:
                item = self._update_queue.get()

                id_ = item
                origin = self._log[str(id_)]['origin']
                file_ = self._log[str(id_)]['file']
                counter = self._log[str(id_)]['counter']
                jobtype = self._log[str(id_)]['jobtype']
                waittime = self._log[str(id_)].get('waittime', 0)
                processtime = self._log[str(id_)].get('processingdate', None)
                globalid = self._log[str(id_)]['globalid']

                laststatus = self._globaljoblog[globalid]['laststatus']
                lastjobid = self._globaljoblog[globalid].get('lastjobid', 0)

                if laststatus is not None and laststatus == 'faulty':
                    # breakup job because last job in chain is faulty
                    logger.error(
                        'Breakup job {} on device {} - File/Job: {} - previous job in chain was broken (ID: {})'
                            .format(str(jobtype), str(origin), str(file_), str(id_)))
                    self._log[id_]['status'] = 'terminated'
                    continue

                if (laststatus is None or laststatus == 'success') and waittime > 0 and processtime is None:
                    # set sleeptime for this job

                    self._log[str(id_)]['processingdate'] = datetime.timestamp(
                        datetime.now() + timedelta(minutes=waittime))

                    self._globaljoblog[globalid]['lastjobid'] = id_
                    self._globaljoblog[globalid]['laststatus'] = 'future'

                    self.add_job(globalid=globalid, origin=origin, file=file_, id_=id_, type=jobtype, counter=counter,
                                 status='future', waittime=waittime, processtime=processtime)

                    continue

                if laststatus is not None and laststatus in ('pending', 'future', 'failure', 'interrupted',
                                                             'not connected') and lastjobid != id_:
                    # skipping because last job in jobchain is not processed till now
                    self.add_job(globalid=globalid, origin=origin, file=file_, id_=id_, type=jobtype, counter=counter,
                                 status='future', waittime=waittime, processtime=processtime)

                    continue

                if processtime is not None and datetime.fromtimestamp(processtime) > datetime.now():
                    self.add_job(globalid=globalid, origin=origin, file=file_, id_=id_, type=jobtype, counter=counter,
                                 status='future', waittime=waittime, processtime=processtime)

                    continue

                if id_ in self._log:
                    self._current_job_id = id_

                    if 'processingdate' in self._log[id_]:
                        del self._log[id_]['processingdate']

                    logger.info(
                        "Job for {} (File/Job: {}) started (ID: {})".format(str(origin), str(file_), str(id_)))
                    self._log[id_]['status'] = 'processing'
                    self._log[id_]['lastprocess'] = int(time.time())
                    self.update_status_log()

                    temp_comm = self._websocket.get_origin_communicator(origin)

                    if temp_comm is None:
                        counter = counter + 1
                        logger.error(
                            'Cannot start job {} on device {} - File/Job: {} - Device not connected (ID: {})'
                                .format(str(jobtype), str(origin), str(file_), str(id_)))
                        self._globaljoblog[globalid]['laststatus'] = 'not connected'
                        self._globaljoblog[globalid]['lastjobid'] = id_
                        self.add_job(globalid=globalid, origin=origin, file=file_, id_=id_, type=jobtype,
                                     counter=counter, status='not connected', waittime=waittime,
                                     processtime=processtime)

                    else:
                        # stop worker
                        self._websocket.set_job_activated(origin)
                        self._log[id_]['status'] = 'starting'
                        self.update_status_log()
                        logger.info(
                            'Job processor waiting for worker start resting - Device {}'.format(str(origin)))
                        # time.sleep(30)
                        try:
                            if self.start_job_type(item, jobtype, temp_comm):
                                logger.info(
                                    'Job {} could be executed successfully - Device {} - File/Job {} (ID: {})'
                                        .format(str(jobtype), str(origin), str(file_), str(id_)))
                                self._log[id_]['status'] = 'success'
                                self._globaljoblog[globalid]['laststatus'] = 'success'
                                self.update_status_log()
                            else:
                                logger.error(
                                    'Job {} could not be executed successfully - Device {} - File/Job {} (ID: {})'
                                        .format(str(jobtype), str(origin), str(file_), str(id_)))
                                counter = counter + 1
                                self._globaljoblog[globalid]['laststatus'] = 'failure'
                                self._globaljoblog[globalid]['lastjobid'] = id_
                                self.add_job(globalid=globalid, origin=origin, file=file_, id_=id_, type=jobtype,
                                             counter=counter, status='failure', waittime=waittime,
                                             processtime=processtime)
                        except:
                            logger.error('Job {} could not be executed successfully (fatal error) '
                                         '- Device {} - File/Job {} (ID: {})'
                                         .format(str(jobtype), str(origin), str(file_), str(id_)))
                            counter = counter + 1
                            self._globaljoblog[globalid]['laststatus'] = 'interrupted'
                            self._globaljoblog[globalid]['lastjobid'] = id_
                            self.add_job(globalid=globalid, origin=origin, file=file_, id_=id_, type=jobtype,
                                         counter=counter, status='interrupted', waittime=waittime,
                                         processtime=processtime)

                        # start worker
                        self._websocket.set_job_deactivated(origin)

                    self._current_job_id = 0

            except KeyboardInterrupt as e:
                logger.info("process_update_queue received keyboard interrupt, stopping")
                break

            time.sleep(5)

    def preadd_job(self, origin, job, id_, type):
        logger.info('Adding Job {} for Device {} - File/Job: {} (ID: {})'
                    .format(str(type), str(origin), str(job), str(id_)))

        globalid = id_

        self._globaljoblog[globalid] = {}
        self._globaljoblog[globalid]['laststatus'] = None
        self._globaljoblog[globalid]['lastjobend'] = None

        if jobType[type.split('.')[1]] == jobType.CHAIN:

            for subjob in self._commands[job]:
                logger.debug(subjob)

                self.add_job(globalid=globalid, origin=origin, file=subjob['SYNTAX'], id_=int(time.time()),
                             type=subjob['TYPE'], waittime=subjob.get('WAITTIME', 0))
                time.sleep(1)
        else:
            self.add_job(globalid=globalid, origin=origin, file=job, id_=int(id_), type=type)

    @logger.catch()
    def add_job(self, globalid, origin, file, id_: int, type, counter=0, status='pending', waittime=0, processtime=None):
        if id_ not in self._log:
            self._log[str(id_)] = {}
            self._log[str(id_)] = ({
                'id': int(id_),
                'origin': origin,
                'file': file,
                'status': status,
                'counter': int(counter),
                'jobtype': str(type),
                'globalid': int(globalid),
                'waittime': waittime
            })
        else:
            self._log[str(id_)]['status'] = status
            self._log[str(id_)]['counter'] = counter

        if counter > 3:
            logger.error("Job for {} (File/Job: {} - Type {}) failed 3 times in row - aborting (ID: {})"
                         .format(str(origin), str(file), str(type), str(id_)))
            self._globaljoblog[globalid]['laststatus'] = 'faulty'
            self._log[id_]['status'] = 'faulty'
        else:
            self._update_queue.put(str(id_))

        self.update_status_log()

    def update_status_log(self):
        self._update_mutex.acquire()
        try:
            with open('update_log.json', 'w') as outfile:
                json.dump(self._log, outfile, indent=4)
        finally:
            self._update_mutex.release()

    @logger.catch()
    def delete_log_id(self, id: str):
        if id != self._current_job_id:
            del self._log[id]
            self.update_status_log()
            return True
        return False

    def get_log(self):
        return self._log

    def start_job_type(self, item, jobtype, ws_conn):
        jobtype = jobType[jobtype.split('.')[1]]
        if jobtype == jobType.INSTALLATION:
            return ws_conn.install_apk(os.path.join(self._args.upload_path, item[2]), 240)
        elif jobtype == jobType.REBOOT:
            return ws_conn.reboot()
        elif jobtype == jobType.RESTART:
            return ws_conn.restartApp("com.nianticlabs.pokemongo")
        elif jobtype == jobType.STOP:
            return ws_conn.stopApp("com.nianticlabs.pokemongo")
        elif jobtype == jobType.START:
            return ws_conn.startApp("com.nianticlabs.pokemongo")
        elif jobtype == jobType.PASSTHROUGH:
            command = item[2]
            returning = ws_conn.passthrough(command).replace('\r', '').replace('\n', '').replace('  ', '')
            self._log[str(item[0])]['returning'] = returning
            self.update_status_log()
            return False if 'KO' in returning else True
        return False

    def delete_log(self):
        for job in self._log.copy():
            self.delete_log_id(job)
