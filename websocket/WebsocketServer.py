import asyncio
import collections
import functools
import math
import queue
from queue import Empty
import sys
import time
import logging
from asyncio import Handle
from threading import Event, Thread, current_thread, Lock
from typing import Optional

import websockets

from utils.MappingManager import MappingManager
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
    def __init__(self, args, mitm_mapper, db_wrapper, mapping_manager, pogoWindowManager,
                 configmode=False):
        self.__current_users = {}
        self.__users_connecting = []

        self.__stop_server = Event()

        self.args = args
        self.__listen_address = args.ws_ip
        self.__listen_port = int(args.ws_port)

        self.__received = {}
        self.__requests = {}

        self.__users_mutex: Optional[asyncio.Lock] = None
        self.__id_mutex: Optional[asyncio.Lock] = None
        self.__send_queue: Optional[asyncio.Queue] = None
        self.__received_mutex: Optional[asyncio.Lock] = None
        self.__requests_mutex: Optional[asyncio.Lock] = None

        self.__db_wrapper = db_wrapper
        self.__mapping_manager: MappingManager = mapping_manager
        self.__pogoWindowManager = pogoWindowManager
        self.__mitm_mapper = mitm_mapper

        self.__next_id = 0
        self._configmode = configmode

        self.__loop = None
        self.__loop_tid = None
        self.__loop_mutex = Lock()
        self.__worker_shutdown_queue: queue.Queue = queue.Queue()
        self.__internal_worker_join_thread: Thread = Thread(name='worker_join_thread',
                                                            target=self.__internal_worker_join)
        self.__internal_worker_join_thread.daemon = True
        self.__internal_worker_join_thread.start()

    def _add_task_to_loop(self, coro):
        f = functools.partial(self.__loop.create_task, coro)
        if current_thread() == self.__loop_tid:
            # We can call directly if we're not going between threads.
            return f()
        else:
            # We're in a non-event loop thread so we use a Future
            # to get the task from the event loop thread once
            # it's ready.
            return self.__loop.call_soon_threadsafe(f)

    def __internal_worker_join(self):
        while not self.__stop_server.is_set():
            try:
                next_item: Optional[Thread] = self.__worker_shutdown_queue.get_nowait()
            except queue.Empty:
                time.sleep(1)
                continue
            if next_item is not None:
                logger.info("Trying to join worker thread")
                next_item.join(10)
                if next_item.isAlive():
                    logger.error("Error while joining worker thread - requeue it")
                    self.__worker_shutdown_queue.put(next_item)
                self.__worker_shutdown_queue.task_done()
                logger.info("Done joining worker thread")

    async def __setup_first_loop(self):
        self.__users_mutex = asyncio.Lock()
        self.__id_mutex = asyncio.Lock()
        self.__send_queue: asyncio.Queue = asyncio.Queue()
        self.__received_mutex = asyncio.Lock()
        self.__requests_mutex = asyncio.Lock()

    def start_server(self):
        logger.info("Starting websocket server...")
        self.__loop = asyncio.new_event_loop()

        logger.debug("Device mappings: {}", str(self.__mapping_manager.get_all_devicemappings()))

        asyncio.set_event_loop(self.__loop)
        self._add_task_to_loop(self.__setup_first_loop())
        self.__loop.run_until_complete(
            websockets.serve(self.handler, self.__listen_address, self.__listen_port, max_size=2 ** 25))
        self.__loop_tid = current_thread()
        self.__loop.run_forever()
        logger.info("Websocketserver stopping...")

    async def __internal_stop_server(self):
        self.__stop_server.set()
        async with self.__users_mutex:
            for id, worker in self.__current_users.items():
                logger.info('Closing connections to device {}.', id)
                await worker[2].close()

        if self.__loop is not None:
            self.__loop.call_soon_threadsafe(self.__loop.stop)

        self.__internal_worker_join_thread.join()

    def stop_server(self):
        with self.__loop_mutex:
            future = asyncio.run_coroutine_threadsafe(self.__internal_stop_server(), self.__loop)
        future.result()

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

    @logger.catch()
    async def __register(self, websocket_client_connection):
        logger.info("Client {} registering", str(
            websocket_client_connection.request_headers.get_all("Origin")[0]))
        if self.__stop_server.is_set():
            logger.info(
                "MAD is set to shut down, not accepting new connection")
            return False

        try:
            origin = str(
                websocket_client_connection.request_headers.get_all("Origin")[0])
        except IndexError:
            logger.warning("Client from {} tried to connect without Origin header", str(
                websocket_client_connection.request_headers.get_all("Origin")[0]))
            return False

        if origin not in self.__mapping_manager.get_all_devicemappings().keys():
            logger.warning("Register attempt of unknown Origin: {}".format(origin))
            return False

        if origin in self.__users_connecting:
            logger.info("Client {} is already connecting".format(origin))
            return False

        auths = self.__mapping_manager.get_auths()
        if auths:
            try:
                authBase64 = str(
                    websocket_client_connection.request_headers.get_all("Authorization")[0])
            except IndexError:
                logger.warning("Client from {} tried to connect without auth header", str(
                    websocket_client_connection.request_headers.get_all("Origin")[0]))
                return False

        async with self.__users_mutex:
            logger.debug("Checking if {} is already present", str(origin))
            if origin in self.__current_users:
                logger.warning(
                    "Worker with origin {} is already running, killing the running one and have client reconnect",
                    str(origin))
                self.__current_users.get(origin)[1].stop_worker()
                ## todo: do this better :D
                logger.info("Old worker thread is still alive - waiting 20 seconds")
                await asyncio.sleep(20)
                logger.info("Reconnect ...")
                return

            self.__users_connecting.append(origin)

        # reset pref. error counter if exist
        await self.__reset_fail_counter(origin)
        try:
            if auths and authBase64 and not check_auth(authBase64, self.args, auths):
                logger.warning("Invalid auth details received from {}", str(
                    websocket_client_connection.request_headers.get_all("Origin")[0]))
                return False
            logger.info("Starting worker {}".format(origin))
            if self._configmode:
                worker = WorkerConfigmode(self.args, origin, self, walker = None,
                                          mapping_manager = self.__mapping_manager, mitm_mapper = self.__mitm_mapper,
                                          db_wrapper = self.__db_wrapper, routemanager_name=None)
                logger.debug("Starting worker for {}", str(origin))
                new_worker_thread = Thread(
                    name='worker_%s' % origin, target=worker.start_worker)
                async with self.__users_mutex:
                    self.__current_users[origin] = [
                        new_worker_thread, worker, websocket_client_connection, 0]
                return True

            last_known_state = {}
            client_mapping = self.__mapping_manager.get_devicemappings_of(origin)
            devicesettings = self.__mapping_manager.get_devicesettings_of(origin)
            logger.info("Setting up routemanagers for {}", str(origin))

            if client_mapping.get("walker", None) is not None:
                if devicesettings is not None and "walker_area_index" not in devicesettings:
                    logger.debug("Initializing devicesettings")
                    self.__mapping_manager.set_devicesetting_value_of(origin, 'walker_area_index', 0)
                    self.__mapping_manager.set_devicesetting_value_of(origin, 'finished', False)
                    self.__mapping_manager.set_devicesetting_value_of(origin, 'last_action_time', None)
                    self.__mapping_manager.set_devicesetting_value_of(origin, 'last_cleanup_time', None)
                    self.__mapping_manager.set_devicesetting_value_of(origin, 'job', False)
                    await asyncio.sleep(1) # give the settings a moment... (dirty "workaround" against race condition)
                walker_index = devicesettings.get('walker_area_index', 0)

                if walker_index > 0:
                    # check status of last area
                    if not devicesettings.get('finished', False):
                        logger.info(
                            'Something wrong with last round - get back to old area')
                        walker_index -= 1
                        self.__mapping_manager.set_devicesetting_value_of(origin, 'walker_area_index', walker_index)
                        # devicesettings['walker_area_index'] = walker_index

                walker_area_array = client_mapping["walker"]
                walker_settings = walker_area_array[walker_index]

                # preckeck walker setting
                while not pre_check_value(walker_settings) and walker_index-1 <= len(walker_area_array):
                    walker_area_name = walker_area_array[walker_index]['walkerarea']
                    logger.info(
                        '{} not using area {} - Walkervalue out of range', str(origin), str(walker_area_name))
                    if walker_index >= len(walker_area_array) - 1:
                        logger.error(
                            'Could not find any working area at this time - check your mappings for device: {}',
                             str(origin))
                        walker_index = 0
                        self.__mapping_manager.set_devicesetting_value_of(origin, 'walker_area_index', walker_index)
                        walker_settings = walker_area_array[walker_index]
                        await websocket_client_connection.close()
                        return
                    walker_index += 1
                    self.__mapping_manager.set_devicesetting_value_of(origin, 'walker_area_index', walker_index)
                    walker_settings = walker_area_array[walker_index]

                devicesettings = self.__mapping_manager.get_devicesettings_of(origin)
                logger.debug("Checking walker_area_index length")
                if (devicesettings.get("walker_area_index", None) is None
                        or devicesettings['walker_area_index'] >= len(walker_area_array)):
                    # check if array is smaller than expected - f.e. on the fly changes in mappings.json
                    self.__mapping_manager.set_devicesetting_value_of(origin, 'walker_area_index', 0)
                    self.__mapping_manager.set_devicesetting_value_of(origin, 'finished', False)
                    walker_index = 0

                walker_area_name = walker_area_array[walker_index]['walkerarea']

                if walker_area_name not in self.__mapping_manager.get_all_routemanager_names():
                    await websocket_client_connection.close()
                    raise WrongAreaInWalker()

                logger.debug('Devicesettings {}: {}', str(origin), devicesettings)
                logger.info('{} using walker area {} [{}/{}]', str(origin), str(
                    walker_area_name), str(walker_index+1), str(len(walker_area_array)))
                walker_routemanager_mode = self.__mapping_manager.routemanager_get_mode(walker_area_name)
                self.__mapping_manager.set_devicesetting_value_of(origin, 'walker_area_index', walker_index+1)
                self.__mapping_manager.set_devicesetting_value_of(origin, 'finished', False)
                if walker_index >= len(walker_area_array) - 1:
                    self.__mapping_manager.set_devicesetting_value_of(origin, 'walker_area_index', 0)

                # set global mon_iv
                routemanager_settings = self.__mapping_manager.routemanager_get_settings(walker_area_name)
                if routemanager_settings is not None:
                    client_mapping['mon_ids_iv'] =\
                        self.__mapping_manager.get_monlist(routemanager_settings.get("mon_ids_iv", None),
                                                           walker_area_name)
            else:
                walker_routemanager_mode = None

            if "last_location" not in devicesettings:
                devicesettings['last_location'] = Location(0.0, 0.0)

            logger.debug("Setting up worker for {}", str(origin))
            worker = None
            if walker_routemanager_mode is None:
                pass
            elif walker_routemanager_mode in ["raids_mitm", "mon_mitm", "iv_mitm"]:
                worker = WorkerMITM(self.args, origin, last_known_state, self, routemanager_name=walker_area_name,
                                    mitm_mapper=self.__mitm_mapper, mapping_manager=self.__mapping_manager,
                                    db_wrapper=self.__db_wrapper,
                                    pogo_window_manager=self.__pogoWindowManager, walker=walker_settings)
            elif walker_routemanager_mode in ["pokestops"]:
                worker = WorkerQuests(self.args, origin, last_known_state, self, routemanager_name=walker_area_name,
                                      mitm_mapper=self.__mitm_mapper, mapping_manager=self.__mapping_manager,
                                      db_wrapper=self.__db_wrapper, pogo_window_manager=self.__pogoWindowManager,
                                      walker=walker_settings)
            elif walker_routemanager_mode in ["idle"]:
                worker = WorkerConfigmode(self.args, origin, self, walker=walker_settings,
                                          mapping_manager=self.__mapping_manager, mitm_mapper=self.__mitm_mapper,
                                          db_wrapper=self.__db_wrapper, routemanager_name=walker_area_name)
            else:
                logger.error("Mode not implemented")
                sys.exit(1)

            if worker is None:
                logger.error("Invalid walker mode for {}. Closing connection".format(str(origin)))
                await websocket_client_connection.close()
            else:
                logger.debug("Starting worker for {}", str(origin))
                new_worker_thread = Thread(
                    name='worker_%s' % origin, target=worker.start_worker)

                new_worker_thread.daemon = True
                async with self.__users_mutex:
                    self.__current_users[origin] = [new_worker_thread,
                                                worker, websocket_client_connection, 0]
                new_worker_thread.start()
        except WrongAreaInWalker:
            logger.error('Unknown Area in Walker settings - check config')
            await websocket_client_connection.close()
        except Exception as e:
            exc_type, exc_value, exc_trace = sys.exc_info()
            logger.error("Other unhandled exception during register: {}\n{}, {}".format(e.with_traceback(None),
                                                                                        exc_value, str(e)))
            await websocket_client_connection.close()
        finally:
            async with self.__users_mutex:
                self.__users_connecting.remove(origin)
            await asyncio.sleep(5)
        return True

    async def __unregister(self, websocket_client_connection):
        # worker_thread: Thread = None
        async with self.__users_mutex:
            worker_id = str(websocket_client_connection.request_headers.get_all("Origin")[0])
            worker = self.__current_users.get(worker_id, None)
            if worker is not None:
                worker[1].stop_worker()
                self.__current_users.pop(worker_id)
        logger.info("Worker {} unregistered", str(worker_id))
        self.__worker_shutdown_queue.put(worker[0])
        # TODO ? worker_thread.join()

    async def __producer_handler(self, websocket_client_connection):
        while websocket_client_connection.open:
            # logger.debug("Connection still open, trying to send next message")
            # retrieve next message from queue to be sent, block if empty
            next = None
            while next is None and websocket_client_connection.open:
                logger.debug("Fetching next message to send")
                next = await self.__retrieve_next_send(websocket_client_connection)
                if next is None:
                    # logger.debug("next is None, stopping connection...")
                    return
                await self.__send_specific(websocket_client_connection, next.id, next.message)

    async def __send_specific(self, websocket_client_connection, id, message):
        # await websocket_client_connection.send(message)
        try:
            user = None
            async with self.__users_mutex:
                for key, value in self.__current_users.items():
                    if key == id and value[2].open:
                        user = value
            if user is not None:
                await user[2].send(message)
        except Exception as e:
            logger.error("Failed sending message in send_specific: {}".format(str(e)))

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
                async with self.__users_mutex:
                    worker = self.__current_users.get(worker_id, None)
                if worker is not None:
                    # TODO: do it abruptly in the worker, maybe set a flag to be checked for in send_and_wait to
                    # TODO: throw an exception
                    worker[1].stop_worker()
                await self.__internal_clean_up_user(worker_id, None)
                return

            if message is not None:
                await self.__on_message(message)
        logger.warning(
            "Connection of {} closed in consumer_handler", str(worker_id))

    async def __internal_clean_up_user(self, worker_id, worker_instance):
        """
        :param worker_id: The ID/Origin of the worker
        :param worker_instance: None if the cleanup is called from within the websocket server
        :return:
        """
        async with self.__users_mutex:
            if worker_id in self.__current_users.keys() and (worker_instance is None
                                                             or self.__current_users[worker_id][1] == worker_instance):
                if self.__current_users[worker_id][2].open:
                    logger.info("Calling close for {}...", str(worker_id))
                    await self.__current_users[worker_id][2].close()
                # self.__current_users.pop(worker_id)
                # logger.info("Info of {} removed in websocket", str(worker_id))

    def clean_up_user(self, worker_id, worker_instance):
        logger.debug2("Cleanup of {} called with ref {}".format(worker_id, str(worker_instance)))
        with self.__loop_mutex:
            future = asyncio.run_coroutine_threadsafe(
                    self.__internal_clean_up_user(worker_id, worker_instance), self.__loop)
        future.result()

    async def __on_message(self, message):
        id = -1
        response = None
        if isinstance(message, str):
            logger.debug("Receiving message: {}", str(message.strip()))
            splitup = message.split(";", 1)
            id = int(splitup[0])
            response = splitup[1]
        else:
            logger.debug("Received binary values.")
            id = int.from_bytes(message[:4], byteorder='big', signed=False)
            response = message[4:]
        await self.__set_response(id, response)
        if not await self.__set_event(id):
            # remove the response again - though that is kinda stupid
            await self.__pop_response(id)

    async def __set_event(self, id):
        result = False
        async with self.__requests_mutex:
            if id in self.__requests:
                self.__requests[id].set()
                result = True
            else:
                # the request has already been deleted due to a timeout...
                logger.error("Request has already been deleted...")
        return result

    async def __set_response(self, id, message):
        async with self.__received_mutex:
            self.__received[id] = message

    async def __pop_response(self, id):
        async with self.__received_mutex:
            message = self.__received.pop(id)
        return message

    async def __get_new_message_id(self):
        async with self.__id_mutex:
            self.__next_id += 1
            self.__next_id = int(math.fmod(self.__next_id, 100000))
            if self.__next_id == 100000:
                self.__next_id = 1
            toBeReturned = self.__next_id
        return toBeReturned

    async def __send(self, id, to_be_sent):
        next_message = OutgoingMessage(id, to_be_sent)
        await self.__send_queue.put(next_message)

    async def __send_and_wait_internal(self, id, worker_instance, message, timeout, byte_command: int = None):
        async with self.__users_mutex:
            user_entry = self.__current_users.get(id, None)

        if user_entry is None or user_entry[1] != worker_instance and worker_instance != 'madmin':
            raise WebsocketWorkerRemovedException

        message_id = await self.__get_new_message_id()
        message_event = asyncio.Event()
        message_event.clear()

        await self.__set_request(message_id, message_event)

        if isinstance(message, str):
            to_be_sent: str = u"%s;%s" % (str(message_id), message)
            logger.debug("To be sent to {}: {}", id, to_be_sent.strip())
        elif byte_command is not None:
            to_be_sent: bytes = (int(message_id)).to_bytes(4, byteorder='big')
            to_be_sent += (int(byte_command)).to_bytes(4, byteorder='big')
            to_be_sent += message
            logger.debug("To be sent to {} (message ID: {}): {}", id, message_id, str(to_be_sent[:10]))
        else:
            logger.fatal("Tried to send invalid message (bytes without byte command or no byte/str passed)")
            return None
        await self.__send(id, to_be_sent)

        # now wait for the response!
        result = None
        logger.debug("Timeout: {}", str(timeout))
        event_triggered = None
        try:
            event_triggered = await asyncio.wait_for(message_event.wait(), timeout=timeout)
        except asyncio.TimeoutError as te:
            logger.warning("Timeout, increasing timeout-counter")
            # TODO: why is the user removed here?
            new_count = await self.__increase_fail_counter(id)
            if new_count > 5:
                logger.error("5 consecutive timeouts to {} or origin is not longer connected, cleanup", str(id))
                await self.__internal_clean_up_user(id, None)
                await self.__reset_fail_counter(id)
                await self.__remove_request(message_id)
                raise WebsocketWorkerTimeoutException

        if event_triggered:
            logger.debug("Received answer in time, popping response")
            await self.__reset_fail_counter(id)
            await self.__remove_request(message_id)
            result = await self.__pop_response(message_id)
            if isinstance(result, str):
                logger.debug("Response to {}: {}",
                             str(id), str(result.strip()))
            else:
                logger.debug("Received binary data to {}, starting with {}", str(
                        id), str(result[:10]))
        return result

    def send_and_wait(self, id, worker_instance, message, timeout, byte_command: int = None):
        if isinstance(message, bytes):
            logger.debug("{} sending binary: {}", str(id), str(message[:10]))
        else:
            logger.debug("{} sending command: {}", str(id), message.strip())
        try:
            # future: Handle = self._add_task_to_loop(self.__send_and_wait_internal(id, worker_instance, message,
            #                                                                       timeout))
            logger.debug("Appending send_and_wait to {}".format(str(self.__loop)))
            with self.__loop_mutex:
                future = asyncio.run_coroutine_threadsafe(
                        self.__send_and_wait_internal(id, worker_instance, message, timeout, byte_command=byte_command), self.__loop)
            result = future.result()
        except WebsocketWorkerRemovedException:
            logger.error("Worker {} was removed, propagating exception".format(id))
            raise WebsocketWorkerRemovedException
        except WebsocketWorkerTimeoutException:
            logger.error("Sending message failed due to timeout ({})".format(id))
            raise WebsocketWorkerTimeoutException
        return result

    async def __set_request(self, id, event):
        async with self.__requests_mutex:
            self.__requests[id] = event

    async def __reset_fail_counter(self, id):
        async with self.__users_mutex:
            if id in self.__current_users.keys():
                self.__current_users[id][3] = 0

    async def __increase_fail_counter(self, id):
        async with self.__users_mutex:
            if id in self.__current_users.keys():
                new_count = self.__current_users[id][3] + 1
                self.__current_users[id][3] = new_count
            else:
                    new_count = 100
        return new_count

    async def __remove_request(self, message_id):
        async with self.__requests_mutex:
            self.__requests.pop(message_id)

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

    def trigger_worker_check_research(self, origin):
        if self.__current_users.get(origin, None) is not None:
            return self.__current_users[origin][1].trigger_check_research()
        return False

    def set_update_sleeptime_worker(self, origin, sleeptime):
        if self.__current_users.get(origin, None) is not None:
            return self.__current_users[origin][1].set_geofix_sleeptime(sleeptime)
        return False

    def set_job_activated(self, origin):
        self.__mapping_manager.set_devicesetting_value_of(origin, 'job', True)

    def set_job_deactivated(self, origin):
        self.__mapping_manager.set_devicesetting_value_of(origin, 'job', False)
