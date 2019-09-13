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


class deviceUpdater(object):
    def __init__(self, websocket, args):
        self._websocket = websocket
        self._update_queue = Queue()
        self._update_mutex = RLock()
        self._log = {}
        self._args = args
        self._current_job_id: int = None
        if os.path.exists('update_log.json'):
            with open('update_log.json') as logfile:
                self._log = json.load(logfile)

        t_updater = Thread(name='apk_updater', target=self.process_update_queue)
        t_updater.daemon = False
        t_updater.start()

    def process_update_queue(self):
        logger.info("Starting Device Job processor")
        while True:
            try:
                item = self._update_queue.get()
                id_, origin, file_, counter, jobtype = (item[0], item[1], item[2], item[4], item[5])

                if id_ in self._log:
                    self._current_job_id = int(id_)

                    logger.info("Job for {} (File: {}) started (ID: {})".format(str(origin), str(file_), str(id_)))
                    self._log[id_]['status'] = 'processing'
                    self.update_status_log()

                    temp_comm = self._websocket.get_origin_communicator(origin)

                    if temp_comm is None:
                        counter = counter + 1
                        logger.error('Cannot start job {} on device {} - File: {} - Device not connected (ID: {})'
                                     .format(str(jobtype), str(origin), str(file_), str(id_)))
                        self.add_job(origin, file_, id_, jobtype, counter, 'not connected')

                    else:
                        # stop worker
                        self._websocket.set_job_activated(origin)
                        if self.start_job_type(item, jobtype, temp_comm):
                            logger.info('Job {} could be executed successfully - Device {} - File {} (ID: {})'
                                         .format(str(jobtype), str(origin), str(file_), str(id_)))
                            self._log[id_]['status'] = 'success'
                            self.update_status_log()
                        else:
                            logger.error('Job {} could not be executed successfully - Device {} - File {} (ID: {})'
                                         .format(str(jobtype), str(origin), str(file_), str(id_)))
                            counter = counter + 1
                            self.add_job(origin, file_, id_, jobtype, counter, 'failure')

                        # start worker
                        self._websocket.set_job_deactivated(origin)

            except KeyboardInterrupt as e:
                logger.info("process_update_queue received keyboard interrupt, stopping")
                break

            time.sleep(5)

    def add_job(self, origin, file, id, type, counter=0, status='pending'):
        logger.info('Adding Job {} for Device {} - File: {} (ID: {})'
                    .format(str(type), str(origin), str(file), str(id)))

        if id not in self._log:
            self._log[id] = {}

        self._log[id] = ({
            'id': id,
            'origin': origin,
            'file': file,
            'status': status,
            'counter': int(counter),
            'jobtype': str(type)
        })

        if counter > 3:
            logger.error("Job for {} (File: {} - Type {}) failed 3 times in row - aborting (ID: {})"
                         .format(str(origin), str(file), str(type), str(id)))
            self._log[id]['status'] = 'faulty'
        else:
            self._update_queue.put((id, origin, file, status, counter, type))

        self.update_status_log()

    def update_status_log(self):
        self._update_mutex.acquire()
        try:
            with open('update_log.json', 'w') as outfile:
                json.dump(self._log, outfile, indent=4)
        finally:
            self._update_mutex.release()

    def delete_log_id(self, id):
        if id in self._log and id != self._current_job_id:
            del self._log[id]
            self.update_status_log()
            return True
        return False

    def get_log(self):
        return self._log

    def start_job_type(self, item, jobtype, ws_conn):
        if jobtype == jobType.INSTALLATION:
            file_ = item[2]
            if ws_conn.install_apk(os.path.join(self._args.upload_path, file_), 240):
                return True
        elif jobtype == jobType.REBOOT:
            if ws_conn.reboot():
                return True
        elif jobtype == jobType.RESTART:
            if ws_conn.restartApp("com.nianticlabs.pokemongo"):
                return True
        elif jobtype == jobType.STOP:
            if ws_conn.stopApp("com.nianticlabs.pokemongo"):
                return True
        return False








