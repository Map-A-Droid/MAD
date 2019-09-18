import json
import os
import time
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
        if os.path.exists('commands.json'):
            with open('commands.json') as logfile:
                self._commands = json.load(logfile)

    @logger.catch()
    def restart_job(self, id_: int):
        if (id_) in self._log:
            origin = self._log[id_]['origin']
            file_ = self._log[id_]['file']
            jobtype = self._log[id_]['jobtype']
            self.add_job(origin, file_, id_, jobtype, counter=0, status='requeued')

        return True

    def kill_old_jobs(self):
        logger.info("Checking for outdated jobs")
        for job in self._log:
            if self._log[job]['status'] in ('pending', 'starting', 'processing', 'not connected'):
                logger.debug("Cancel job {} - it is outdated".format(str(job)))
                self._log[job]['status'] = 'canceled'
                self.update_status_log()

    logger.catch()
    def process_update_queue(self):
        logger.info("Starting Device Job processor")
        while True:
            try:
                item = self._update_queue.get()
                id_, origin, file_, counter, jobtype = (item[0], item[1], item[2], item[4], item[5])

                if id_ in self._log:
                    self._current_job_id = id_

                    logger.info("Job for {} (File/Job: {}) started (ID: {})".format(str(origin), str(file_), str(id_)))
                    self._log[id_]['status'] = 'processing'
                    self.update_status_log()

                    temp_comm = self._websocket.get_origin_communicator(origin)

                    if temp_comm is None:
                        counter = counter + 1
                        logger.error('Cannot start job {} on device {} - File/Job: {} - Device not connected (ID: {})'
                                     .format(str(jobtype), str(origin), str(file_), str(id_)))
                        self.add_job(origin, file_, id_, jobtype, counter, 'not connected')

                    else:
                        # stop worker
                        self._websocket.set_job_activated(origin)
                        self._log[id_]['status'] = 'starting'
                        self.update_status_log()
                        logger.info('Job processor waiting for worker start resting - Device {}'.format(str(origin)))
                        #time.sleep(30)
                        try:
                            if self.start_job_type(item, jobtype, temp_comm):
                                logger.info('Job {} could be executed successfully - Device {} - File/Job {} (ID: {})'
                                             .format(str(jobtype), str(origin), str(file_), str(id_)))
                                self._log[id_]['status'] = 'success'
                                self.update_status_log()
                            else:
                                logger.error('Job {} could not be executed successfully - Device {} - File/Job {} (ID: {})'
                                             .format(str(jobtype), str(origin), str(file_), str(id_)))
                                counter = counter + 1
                                self.add_job(origin, file_, id_, jobtype, counter, 'failure')
                        except:
                            logger.error('Job {} could not be executed successfully (fatal error) '
                                         '- Device {} - File/Job {} (ID: {})'
                                         .format(str(jobtype), str(origin), str(file_), str(id_)))
                            counter = counter + 1
                            self.add_job(origin, file_, id_, jobtype, counter, 'interrupted')

                        # start worker
                        self._websocket.set_job_deactivated(origin)

                    self._current_job_id = 0

            except KeyboardInterrupt as e:
                logger.info("process_update_queue received keyboard interrupt, stopping")
                break

            time.sleep(5)

    def preadd_job(self, origin, job, id_, type):
        if jobType[type.split('.')[1]] == jobType.CHAIN:
            logger.info('Processing Jobchain {} for Device {} (ID: {})'
                        .format(str(job), str(origin), str(id_)))
            for subjob in self._commands[job]:
                self.add_job(origin, subjob['SYNTAX'], int(time.time()), subjob['TYPE'])
                time.sleep(1)
        else:
            self.add_job(origin, job, int(id_), type)

    def add_job(self, origin, file, id_: int, type, counter=0, status='pending'):
        logger.info('Adding Job {} for Device {} - File/Job: {} (ID: {})'
                    .format(str(type), str(origin), str(file), str(id_)))

        if id_ not in self._log:
            self._log[str(id_)] = {}

        self._log[str(id_)] = ({
            'id': int(id_),
            'origin': origin,
            'file': file,
            'status': status,
            'counter': int(counter),
            'jobtype': str(type)
        })

        if counter > 3:
            logger.error("Job for {} (File/Job: {} - Type {}) failed 3 times in row - aborting (ID: {})"
                         .format(str(origin), str(file), str(type), str(id_)))
            self._log[id_]['status'] = 'faulty'
        else:
            self._update_queue.put((str(id_), origin, file, status, counter, type))

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
            return True
        return False

    def delete_log(self):
        for job in self._log.copy():
            self.delete_log_id(job)
