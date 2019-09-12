import json
import os
import time
from multiprocessing import  Queue
from threading import  RLock, Thread
from utils.logging import logger

class deviceUpdater(object):
    def __init__(self, websocket, args):
        self._websocket = websocket
        self._update_queue = Queue()
        self._update_mutex = RLock()
        self._log = {}
        self._args = args
        if os.path.exists('update_log.json'):
            with open('update_log.json') as logfile:
                self._log = json.load(logfile)

        t_updater = Thread(name='apk_updater', target=self.process_update_queue)
        t_updater.daemon = False
        t_updater.start()

    def process_update_queue(self):
        logger.info("Starting Device Updater processor")
        while True:
            try:
                item = self._update_queue.get()
                id_, origin, file_, counter = (item[0], item[1], item[2], item[4])

                logger.info("Update for {} (File: {}) started".format(str(origin), str(file)))
                self._log[id]['status'] = 'processing'
                self.update_status_log()

                temp_comm = self._websocket.get_origin_communicator(origin)
                if temp_comm is None:
                    counter = counter + 1
                    logger.error('Cannot update device {} with {} - Device not connected'
                                 .format(str(origin), str(file_)))
                    self.add_update(origin, file_, id_, counter, 'not connected')

                else:
                    if temp_comm.install_apk(os.path.join(self._args.upload_path, file_), 240):
                        self._log[id]['status'] = 'success'
                        self.update_status_log()
                    else:
                        logger.error('Cannot update device {} with {} - Installations failed'
                                     .format(str(origin), str(file_)))
                        self.add_update(origin, file_, id_, counter, 'failure')

                time.sleep(5)

            except KeyboardInterrupt as e:
                logger.info("process_update_queue received keyboard interrupt, stopping")
                break

            time.sleep(5)

    def add_update(self, origin, file, id, counter=0, status='pending'):
        logger.info('Adding App Update for Device {} - File: {} (ID: {})'.format(str(origin), str(file), str(id)))
        if id in self._log:
            self._log[id] = ({
                'id': id,
                'origin': origin,
                'file': file,
                'status': status,
                'counter': int(counter)
            })
        else:
            self._log[id] = {}
            self._log[id] = ({
                'id': id,
                'origin': origin,
                'file': file,
                'status': status,
                'counter': int(counter)
            })

        if counter > 3:
            logger.error("Update for {} (File: {}) failed 3 times in row - aborting".format(str(origin), str(file)))
            self._log[id]['status'] = 'abort'
        else:
            self._update_queue.put((id, origin, file, status, counter))

        self.update_status_log()

    def update_status_log(self):
        self._update_mutex.acquire()
        try:
            with open('update_log.json', 'w') as outfile:
                json.dump(self._log, outfile, indent=4)
        finally:
            self._update_mutex.release()

    def delete_log_id(self, id):
        if id in self._log:
            del self._log[id]
            self.update_status_log()

    def get_log(self):
        return self._log




