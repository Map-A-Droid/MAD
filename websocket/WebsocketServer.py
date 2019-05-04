import asyncio
import collections
import math
import queue
import sys
import time
import logging
from threading import Event, Lock, Thread

import websockets
from utils.authHelper import check_auth
from utils.logging import logger, InterceptHandler
from utils.madGlobals import (WebsocketWorkerRemovedException,
                              WebsocketWorkerTimeoutException,
                              WrongAreaInWalker)
from utils.routeutil import pre_check_value
from worker.WorkerConfigmode import WorkerConfigmode
from worker.WorkerMITM import WorkerMITM
from worker.WorkerQuests import WorkerQuests

OutgoingMessage = collections.namedtuple('OutgoingMessage', ['id', 'message'])
Location = collections.namedtuple('Location', ['lat', 'lng'])

logging.getLogger('websockets.server').setLevel(logging.DEBUG)
logging.getLogger('websockets.protocol').setLevel(logging.DEBUG)
logging.getLogger('websockets.server').addHandler(InterceptHandler())
logging.getLogger('websockets.protocol').addHandler(InterceptHandler())


class WebsocketServer(object):
    def __init__(self, args, mitm_mapper, db_wrapper, routemanagers, device_mappings, auths, pogoWindowManager,
                 configmode=False):
        self.__current_users = {}
        self.__current_users_mutex = Lock()
        self.__stop_server = Event()

        self.args = args
        self.__listen_address = args.ws_ip
        self.__listen_port = int(args.ws_port)

        self.__send_queue = queue.Queue()

        self.__received = {}
        self.__received_mutex = Lock()
        self.__requests = {}
        self.__requests_mutex = Lock()

        self.__db_wrapper = db_wrapper
        self.__device_mappings = device_mappings
        self.__routemanagers = routemanagers
        self.__auths = auths
        self.__pogoWindowManager = pogoWindowManager
        self.__mitm_mapper = mitm_mapper

        self.__next_id = 0
        self.__id_mutex = Lock()
        self._configmode = configmode

        self.__loop = None

    def start_server(self):
        logger.info("Starting websocket server...")
        self.__loop = asyncio.new_event_loop()
        # build list of origin IDs
        allowed_origins = []
        for device in self.__device_mappings.keys():
            allowed_origins.append(device)

        logger.debug("Device mappings: {}", str(self.__device_mappings))
        logger.debug("Allowed origins derived: {}", str(allowed_origins))

        asyncio.set_event_loop(self.__loop)
        self.__loop.run_until_complete(
            websockets.serve(self.handler, self.__listen_address, self.__listen_port, max_size=2 ** 25,
                             origins=allowed_origins, ping_timeout=10, ping_interval=15))
        self.__loop.run_forever()

    def stop_server(self):
        # TODO: cleanup workers...
        self.__stop_server.set()
        self.__current_users_mutex.acquire()
        for id, worker in self.__current_users.items():
            logger.info('Stopping worker {} to apply new mappings.', id)
            worker[1].stop_worker()
        self.__current_users_mutex.release()

        # wait for all workers to be stopped...
        while True:
            self.__current_users_mutex.acquire()
            if len(self.__current_users) == 0:
                self.__current_users_mutex.release()
                break
            else:
                self.__current_users_mutex.release()
                time.sleep(1)
        for routemanager in self.__routemanagers.keys():
            area = self.__routemanagers.get(routemanager, None)
            if area is None:
                continue
            area["routemanager"].stop_routemanager()

        if self.__loop is not None:
            self.__loop.call_soon_threadsafe(self.__loop.stop)

    async def handler(self, websocket_client_connection, path):
        logger.info("Waiting for connection...")
        # wait for a connection...
        continue_work = await self.__register(websocket_client_connection)
        if not continue_work:
            logger.error("Failed registering client, closing connection")
            await websocket_client_connection.close()
            return

        consumer_task = asyncio.ensure_future(
            self.__consumer_handler(websocket_client_connection))
        producer_task = asyncio.ensure_future(
            self.__producer_handler(websocket_client_connection))
        done, pending = await asyncio.wait(
            [producer_task, consumer_task],
            return_when=asyncio.FIRST_COMPLETED,
        )
        logger.info("consumer or producer of {} stopped, cancelling pending tasks", str(
            websocket_client_connection.request_headers.get_all("Origin")[0]))
        for task in pending:
            task.cancel()
        logger.info("Awaiting unregister of {}", str(
            websocket_client_connection.request_headers.get_all("Origin")[0]))
        await self.__unregister(websocket_client_connection)
        logger.info("All done with {}", str(
            websocket_client_connection.request_headers.get_all("Origin")[0]))

    async def __register(self, websocket_client_connection):
        logger.info("Client {} registering", str(
            websocket_client_connection.request_headers.get_all("Origin")[0]))
        if self.__stop_server.is_set():
            logger.info(
                "MAD is set to shut down, not accepting new connection")
            return False

        try:
            id = str(
                websocket_client_connection.request_headers.get_all("Origin")[0])
        except IndexError:
            logger.warning("Client from {} tried to connect without Origin header", str(
                websocket_client_connection.request_headers.get_all("Origin")[0]))
            return False

        if self.__auths:
            try:
                authBase64 = str(
                    websocket_client_connection.request_headers.get_all("Authorization")[0])
            except IndexError:
                logger.warning("Client from {} tried to connect without auth header", str(
                    websocket_client_connection.request_headers.get_all("Origin")[0]))
                return False

        self.__current_users_mutex.acquire()
        try:
            logger.debug("Checking if {} is already present", str(id))
            user_present = self.__current_users.get(id)
            if user_present is not None:
                logger.warning("Worker with origin {} is already running, killing the running one and have client reconnect",
                               str(websocket_client_connection.request_headers.get_all("Origin")[0]))
                user_present[1].stop_worker()
                return False
            elif self.__auths and authBase64 and not check_auth(authBase64, self.args, self.__auths):
                logger.warning("Invalid auth details received from {}", str(
                    websocket_client_connection.request_headers.get_all("Origin")[0]))
                return False

            if self._configmode:
                worker = WorkerConfigmode(self.args, id, self)
                logger.debug("Starting worker for {}", str(id))
                new_worker_thread = Thread(
                    name='worker_%s' % id, target=worker.start_worker)
                self.__current_users[id] = [
                    new_worker_thread, worker, websocket_client_connection, 0]
                return True

            last_known_state = {}
            client_mapping = self.__device_mappings[id]
            devicesettings = client_mapping["settings"]
            logger.info("Setting up routemanagers for {}", str(id))

            if client_mapping.get("walker", None) is not None:
                if "walker_area_index" not in devicesettings:
                    devicesettings['walker_area_index'] = 0
                    devicesettings['finished'] = False
                    devicesettings['last_action_time'] = None
                    devicesettings['last_cleanup_time'] = None

                walker_index = devicesettings.get('walker_area_index', 0)

                if walker_index > 0:
                    # check status of last area
                    if not devicesettings.get('finished', False):
                        logger.info(
                            'Something wrong with last round - get back to old area')
                        walker_index -= 1
                        devicesettings['walker_area_index'] = walker_index

                walker_area_array = client_mapping["walker"]
                walker_settings = walker_area_array[walker_index]

                # preckeck walker setting
                while not pre_check_value(walker_settings) and walker_index-1 <= len(walker_area_array):
                    walker_area_name = walker_area_array[walker_index]['walkerarea']
                    logger.info(
                        '{} dont using area {} - Walkervalue out of range', str(id), str(walker_area_name))
                    if walker_index >= len(walker_area_array) - 1:
                        logger.error(
                            'Dont find any working area - check your config')
                        walker_index = 0
                        devicesettings['walker_area_index'] = walker_index
                        walker_settings = walker_area_array[walker_index]
                        break
                    walker_index += 1
                    devicesettings['walker_area_index'] = walker_index
                    walker_settings = walker_area_array[walker_index]

                if devicesettings['walker_area_index'] >= len(walker_area_array):
                    # check if array is smaller then expected - f.e. on the fly changes in mappings.json
                    devicesettings['walker_area_index'] = 0
                    devicesettings['finished'] = False
                    walker_index = devicesettings.get('walker_area_index', 0)

                walker_area_name = walker_area_array[walker_index]['walkerarea']

                if walker_area_name not in self.__routemanagers:
                    raise WrongAreaInWalker()

                logger.debug('Devicesettings {}: {}', str(id), devicesettings)
                logger.info('{} using walker area {} [{}/{}]', str(id), str(
                    walker_area_name), str(walker_index+1), str(len(walker_area_array)))
                walker_routemanager = \
                    self.__routemanagers[walker_area_name].get(
                        "routemanager", None)
                devicesettings['walker_area_index'] += 1
                devicesettings['finished'] = False
                if walker_index >= len(walker_area_array) - 1:
                    devicesettings['walker_area_index'] = 0

                # set global mon_iv
                client_mapping['mon_ids_iv'] = \
                    self.__routemanagers[walker_area_name].get(
                        "routemanager").settings.get("mon_ids_iv", [])

            else:
                walker_routemanager = None

            if "last_location" not in devicesettings:
                devicesettings['last_location'] = Location(0.0, 0.0)

            logger.debug("Setting up worker for {}", str(id))

            if walker_routemanager is None:
                pass
            elif walker_routemanager.mode in ["raids_mitm", "mon_mitm", "iv_mitm"]:
                worker = WorkerMITM(self.args, id, last_known_state, self, walker_routemanager,
                                    self.__mitm_mapper, devicesettings, db_wrapper=self.__db_wrapper,
                                    pogoWindowManager=self.__pogoWindowManager, walker=walker_settings)
            elif walker_routemanager.mode in ["raids_ocr"]:
                from worker.WorkerOCR import WorkerOCR
                worker = WorkerOCR(self.args, id, last_known_state, self, walker_routemanager,
                                   devicesettings, db_wrapper=self.__db_wrapper,
                                   pogoWindowManager=self.__pogoWindowManager, walker=walker_settings)
            elif walker_routemanager.mode in ["pokestops"]:
                worker = WorkerQuests(self.args, id, last_known_state, self, walker_routemanager,
                                      self.__mitm_mapper, devicesettings, db_wrapper=self.__db_wrapper,
                                      pogoWindowManager=self.__pogoWindowManager, walker=walker_settings)
            elif walker_routemanager.mode in ["idle"]:
                worker = WorkerConfigmode(self.args, id, self)
            else:
                logger.error("Mode not implemented")
                sys.exit(1)

            logger.debug("Starting worker for {}", str(id))
            new_worker_thread = Thread(
                name='worker_%s' % id, target=worker.start_worker)

            new_worker_thread.daemon = False

            self.__current_users[id] = [new_worker_thread,
                                        worker, websocket_client_connection, 0]
            new_worker_thread.start()
        except WrongAreaInWalker:
            logger.error('Unknown Area in Walker settings - check config')
        finally:
            self.__current_users_mutex.release()

        return True

    async def __unregister(self, websocket_client_connection):
        worker_id = str(
            websocket_client_connection.request_headers.get_all("Origin")[0])
        self.__current_users_mutex.acquire()
        worker = self.__current_users.get(worker_id, None)
        if worker is not None:
            self.__current_users.pop(worker_id)
        self.__current_users_mutex.release()
        logger.info("Worker {} unregistered", str(worker_id))

    async def __producer_handler(self, websocket_client_connection):
        while websocket_client_connection.open:
            # logger.debug("Connection still open, trying to send next message")
            # retrieve next message from queue to be sent, block if empty
            next = None
            while next is None and websocket_client_connection.open:
                logger.debug("Retrieving next message to send")
                next = await self.__retrieve_next_send(websocket_client_connection)
                if next is None:
                    # logger.debug("next is None, stopping connection...")
                    return
                await self.__send_specific(websocket_client_connection, next.id, next.message)

    async def __send_specific(self, websocket_client_connection, id, message):
        # await websocket_client_connection.send(message)
        for key, value in self.__current_users.items():
            if key == id and value[2].open:
                await value[2].send(message)

    async def __retrieve_next_send(self, websocket_client_connection):
        found = None
        while found is None and websocket_client_connection.open:
            try:
                found = self.__send_queue.get_nowait()
            except Exception as e:
                await asyncio.sleep(0.02)
        if not websocket_client_connection.open:
            logger.warning(
                "retrieve_next_send: connection closed, returning None")
        return found

    async def __consumer_handler(self, websocket_client_connection):
        if websocket_client_connection is None:
            return
        worker_id = str(
            websocket_client_connection.request_headers.get_all("Origin")[0])
        logger.info("Consumer handler of {} starting", str(worker_id))
        while websocket_client_connection.open:
            message = None
            try:
                message = await asyncio.wait_for(websocket_client_connection.recv(), timeout=2.0)
            except asyncio.TimeoutError as te:
                await asyncio.sleep(0.02)
            except websockets.exceptions.ConnectionClosed as cc:
                logger.warning(
                    "Connection to {} was closed, stopping worker", str(worker_id))
                self.__current_users_mutex.acquire()
                worker = self.__current_users.get(worker_id, None)
                self.__current_users_mutex.release()
                if worker is not None:
                    # TODO: do it abruptly in the worker, maybe set a flag to be checked for in send_and_wait to
                    # TODO: throw an exception
                    worker[1].stop_worker()
                self.clean_up_user(worker_id, None)
                return

            if message is not None:
                await self.__on_message(message)
        logger.warning(
            "Connection of {} closed in consumer_handler", str(worker_id))

    def clean_up_user(self, worker_id, worker_instance):
        """
        :param worker_id: The ID/Origin of the worker
        :param worker_instance: None if the cleanup is called from within the websocket server
        :return:
        """
        self.__current_users_mutex.acquire()
        if worker_id in self.__current_users.keys() and (worker_instance is None
                                                         or self.__current_users[worker_id][1] == worker_instance):
            if self.__current_users[worker_id][2].open:
                logger.info("Calling close for {}...", str(worker_id))
                asyncio.ensure_future(
                    self.__current_users[worker_id][2].close(), loop=self.__loop)
            self.__current_users.pop(worker_id)
            logger.info("Info of {} removed in websocket", str(worker_id))
        self.__current_users_mutex.release()

    async def __on_message(self, message):
        id = -1
        response = None
        if isinstance(message, str):
            logger.debug("Receiving message: {}", str(message.strip()))
            splitup = message.split(";")
            id = int(splitup[0])
            response = splitup[1]
        else:
            logger.debug("Received binary values.")
            id = int.from_bytes(message[:4], byteorder='big', signed=False)
            response = message[4:]
        await self.__set_response(id, response)
        if not await self.__set_event(id):
            # remove the response again - though that is kinda stupid
            self.__pop_response(id)

    async def __set_event(self, id):
        result = False
        self.__requests_mutex.acquire()
        if id in self.__requests:
            self.__requests[id].set()
            result = True
        else:
            # the request has already been deleted due to a timeout...
            logger.error("Request has already been deleted...")
        self.__requests_mutex.release()
        return result

    async def __set_response(self, id, message):
        self.__received_mutex.acquire()
        self.__received[id] = message
        self.__received_mutex.release()

    def __pop_response(self, id):
        self.__received_mutex.acquire()
        message = self.__received.pop(id)
        self.__received_mutex.release()
        return message

    def __get_new_message_id(self):
        self.__id_mutex.acquire()
        self.__next_id += 1
        self.__next_id = int(math.fmod(self.__next_id, 100000))
        if self.__next_id == 100000:
            self.__next_id = 1
        toBeReturned = self.__next_id
        self.__id_mutex.release()
        return toBeReturned

    def __send(self, id, to_be_sent):
        next_message = OutgoingMessage(id, to_be_sent)
        self.__send_queue.put(next_message)

    def send_and_wait(self, id, worker_instance, message, timeout):
        logger.debug("{} sending command: {}", str(id), message.strip())
        self.__current_users_mutex.acquire()
        user_entry = self.__current_users.get(id, None)
        self.__current_users_mutex.release()

        if user_entry is None or user_entry[1] != worker_instance and worker_instance != 'madmin':
            raise WebsocketWorkerRemovedException

        message_id = self.__get_new_message_id()
        message_event = Event()
        message_event.clear()

        self.__set_request(message_id, message_event)

        to_be_sent = u"%s;%s" % (str(message_id), message)
        logger.debug("To be sent: {}", to_be_sent.strip())
        self.__send(id, to_be_sent)

        # now wait for the response!
        result = None
        logger.debug("Timeout: {}", str(timeout))
        if message_event.wait(timeout):
            logger.debug("Received answer in time, popping response")
            self.__reset_fail_counter(id)
            result = self.__pop_response(message_id)
            if isinstance(result, str):
                logger.debug("Response to {}: {}",
                             str(id), str(result.strip()))
            else:
                logger.debug("Received binary data to {}, starting with {}", str(
                    id), str(result[:10]))
        else:
            # timeout reached
            logger.warning("Timeout, increasing timeout-counter")
            # TODO: why is the user removed here?
            new_count = self.__increase_fail_counter(id)
            if new_count > 5:
                logger.error("5 consecutive timeouts to {}, cleanup", str(id))
                # TODO: signal worker to stop and NOT cleanup the websocket by itself!
                self.clean_up_user(id, None)
                raise WebsocketWorkerTimeoutException

        self.__remove_request(message_id)
        return result

    def __set_request(self, id, event):
        self.__requests_mutex.acquire()
        self.__requests[id] = event
        self.__requests_mutex.release()

    def __reset_fail_counter(self, id):
        self.__current_users_mutex.acquire()
        if id in self.__current_users.keys():
            self.__current_users[id][3] = 0
        self.__current_users_mutex.release()

    def __increase_fail_counter(self, id):
        self.__current_users_mutex.acquire()
        if id in self.__current_users.keys():
            new_count = self.__current_users[id][3] + 1
            self.__current_users[id][3] = new_count
        else:
            new_count = 100
        self.__current_users_mutex.release()
        return new_count

    def __remove_request(self, message_id):
        self.__requests_mutex.acquire()
        self.__requests.pop(message_id)
        self.__requests_mutex.release()

    def update_settings(self, routemanagers, device_mappings, auths):
        for dev in self.__device_mappings:
            if "last_location" in self.__device_mappings[dev]['settings']:
                device_mappings[dev]['settings']["last_location"] = \
                    self.__device_mappings[dev]['settings']["last_location"]
            if "walker_area_index" in self.__device_mappings[dev]['settings']:
                device_mappings[dev]['settings']["walker_area_index"] = \
                    self.__device_mappings[dev]['settings']["walker_area_index"]
            if "last_mode" in self.__device_mappings[dev]['settings']:
                device_mappings[dev]['settings']["last_mode"] = \
                    self.__device_mappings[dev]['settings']["last_mode"]
        self.__current_users_mutex.acquire()
        # save reference to old routemanagers to stop them
        old_routemanagers = routemanagers
        self.__device_mappings = device_mappings
        self.__routemanagers = routemanagers
        self.__auths = auths
        for id, worker in self.__current_users.items():
            logger.info('Stopping worker {} to apply new mappings.', id)
            worker[1].stop_worker()
        self.__current_users_mutex.release()
        for routemanager in old_routemanagers.keys():
            area = routemanagers.get(routemanager, None)
            if area is None:
                continue
            area["routemanager"].stop_routemanager()

    def get_reg_origins(self):
        return self.__current_users

    def get_origin_communicator(self, origin):
        if self.__current_users.get(origin, None) is not None:
            return self.__current_users[origin][1].get_communicator()
        return None

    def set_geofix_sleeptime_worker(self, origin, sleeptime):
        if self.__current_users.get(origin, None) is not None:
            return self.__current_users[origin][1].set_geofix_sleeptime(sleeptime)
        return False
