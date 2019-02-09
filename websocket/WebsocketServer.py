import asyncio
import collections
import logging
import math
import queue
import sys
import time
from threading import Event, Lock, Thread

import websockets
from utils.authHelper import check_auth
from utils.madGlobals import (WebsocketWorkerRemovedException,
                              WebsocketWorkerTimeoutException)
from utils.timer import Timer
from worker.WorkerMITM import WorkerMITM
from worker.WorkerQuests import WorkerQuests

log = logging.getLogger(__name__)
OutgoingMessage = collections.namedtuple('OutgoingMessage', ['id', 'message'])


class WebsocketServer(object):
    def __init__(self, args, mitm_mapper, db_wrapper, routemanagers, device_mappings, auths):
        self.__current_users = {}
        self.__current_users_mutex = Lock()

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
        self.__mitm_mapper = mitm_mapper

        self.__next_id = 0
        self.__id_mutex = Lock()

        self.__loop = None

    def start_server(self):
        log.info("Starting websocket server...")
        self.__loop = asyncio.new_event_loop()
        # build list of origin IDs
        allowed_origins = []
        for device in self.__device_mappings.keys():
            allowed_origins.append(device)

        log.info("Device mappings: %s" % str(self.__device_mappings))
        log.info("Allowed origins derived: %s" % str(allowed_origins))
        asyncio.set_event_loop(self.__loop)
        asyncio.get_event_loop().run_until_complete(
            websockets.serve(self.handler, self.__listen_address, self.__listen_port, max_size=2 ** 25,
                             origins=allowed_origins, ping_timeout=10, ping_interval=15))
        asyncio.get_event_loop().run_forever()

    async def handler(self, websocket_client_connection, path):
        log.info("Waiting for connection...")
        # wait for a connection...
        continue_work = await self.__register(websocket_client_connection)
        if not continue_work:
            log.error("Failed registering client, closing connection")
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
        log.info("consumer or producer of %s stopped, cancelling pending tasks"
                 % str(websocket_client_connection.request_headers.get_all("Origin")[0]))
        for task in pending:
            task.cancel()
        log.info("Awaiting unregister of %s" % str(
            websocket_client_connection.request_headers.get_all("Origin")[0]))
        await self.__unregister(websocket_client_connection)
        log.info("All done with %s" % str(
            websocket_client_connection.request_headers.get_all("Origin")[0]))

    async def __register(self, websocket_client_connection):
        log.info("Client %s registering" % str(
            websocket_client_connection.request_headers.get_all("Origin")[0]))
        try:
            id = str(
                websocket_client_connection.request_headers.get_all("Origin")[0])
        except IndexError:
            log.warning("Client from %s tried to connect without Origin header"
                        % str(websocket_client_connection.request_headers.get_all("Origin")[0]))
            return False

        if self.__auths:
            try:
                authBase64 = str(
                    websocket_client_connection.request_headers.get_all("Authorization")[0])
            except IndexError:
                log.warning("Client from %s tried to connect without auth header"
                            % str(websocket_client_connection.request_headers.get_all("Origin")[0]))
                return False

        self.__current_users_mutex.acquire()
        user_present = self.__current_users.get(id)
        if user_present is not None:
            log.warning("Worker with origin %s is already running, killing the running one and have client reconnect"
                        % str(websocket_client_connection.request_headers.get_all("Origin")[0]))
            user_present[1].stop_worker()
            self.__current_users_mutex.release()
            return False
        elif self.__auths and authBase64 and not check_auth(authBase64, self.args, self.__auths):
            log.warning("Invalid auth details received from %s"
                        % str(websocket_client_connection.request_headers.get_all("Origin")[0]))
            self.__current_users_mutex.release()
            return False
        self.__current_users_mutex.release()

        last_known_state = {}
        client_mapping = self.__device_mappings[id]
        timer = Timer(client_mapping["switch"], id,
                      client_mapping["switch_interval"])
        await asyncio.sleep(0.8)
        daytime_routemanager = self.__routemanagers[client_mapping["daytime_area"]].get(
            "routemanager")
        if client_mapping.get("nighttime_area", None) is not None:
            nightime_routemanager = self.__routemanagers[client_mapping["nighttime_area"]].get(
                "routemanager", None)
        else:
            nightime_routemanager = None
        devicesettings = client_mapping["settings"]

        started = False
        if timer.get_switch() is True:
            # set global mon_iv
            client_mapping['mon_ids_iv'] = self.__routemanagers[client_mapping["nighttime_area"]].get(
                "routemanager").settings.get("mon_ids_iv", [])
            # start the appropriate nighttime manager if set
            if nightime_routemanager is None:
                pass
            elif nightime_routemanager.mode in ["raids_mitm", "mon_mitm", "iv_mitm"]:
                worker = WorkerMITM(self.args, id, last_known_state, self, daytime_routemanager, nightime_routemanager,
                                    self.__mitm_mapper, devicesettings, db_wrapper=self.__db_wrapper, timer=timer)
                started = True
            elif nightime_routemanager.mode in ["raids_ocr"]:
                from worker.WorkerOCR import WorkerOCR
                worker = WorkerOCR(self.args, id, last_known_state, self, daytime_routemanager, nightime_routemanager,
                                   devicesettings, db_wrapper=self.__db_wrapper, timer=timer)
                started = True
            elif nightime_routemanager.mode in ["pokestops"]:
                worker = WorkerQuests(self.args, id, last_known_state, self, daytime_routemanager, nightime_routemanager,
                                      self.__mitm_mapper, devicesettings, db_wrapper=self.__db_wrapper, timer=timer)
                started = True
            else:
                log.fatal("Mode not implemented")
                sys.exit(1)
        if not timer.get_switch() or not started:
            # set mon_iv
            client_mapping['mon_ids_iv'] = self.__routemanagers[client_mapping["daytime_area"]].get(
                "routemanager").settings.get("mon_ids_iv", [])
            # we either gotta run daytime mode OR nighttime routemanager not set
            if daytime_routemanager.mode in ["raids_mitm", "mon_mitm", "iv_mitm"]:
                worker = WorkerMITM(self.args, id, last_known_state, self, daytime_routemanager, nightime_routemanager,
                                    self.__mitm_mapper, devicesettings, db_wrapper=self.__db_wrapper, timer=timer)
            elif daytime_routemanager.mode in ["raids_ocr"]:
                from worker.WorkerOCR import WorkerOCR
                worker = WorkerOCR(self.args, id, last_known_state, self, daytime_routemanager, nightime_routemanager,
                                   devicesettings, db_wrapper=self.__db_wrapper, timer=timer)
            elif daytime_routemanager.mode in ["pokestops"]:
                worker = WorkerQuests(self.args, id, last_known_state, self, daytime_routemanager, nightime_routemanager,
                                      self.__mitm_mapper, devicesettings, db_wrapper=self.__db_wrapper, timer=timer)
            else:
                log.fatal("Mode not implemented")
                sys.exit(1)

        new_worker_thread = Thread(name='worker_%s' %
                                   id, target=worker.start_worker)
        new_worker_thread.daemon = True
        self.__current_users_mutex.acquire()
        self.__current_users[id] = [new_worker_thread,
                                    worker, websocket_client_connection, 0]
        self.__current_users_mutex.release()
        new_worker_thread.start()

        return True

    async def __unregister(self, websocket_client_connection):
        id = str(
            websocket_client_connection.request_headers.get_all("Origin")[0])
        self.__current_users_mutex.acquire()
        worker = self.__current_users.get(id, None)
        if worker is not None:
            self.__current_users.pop(id)
        self.__current_users_mutex.release()

    async def __producer_handler(self, websocket_client_connection):
        while websocket_client_connection.open:
            # log.debug("Connection still open, trying to send next message")
            # retrieve next message from queue to be sent, block if empty
            next = None
            while next is None and websocket_client_connection.open:
                log.debug("Retrieving next message to send")
                next = await self.__retrieve_next_send(websocket_client_connection)
                if next is None:
                    # log.debug("next is None, stopping connection...")
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
            log.error("retrieve_next_send: connection closed, returning None")
        return found

    async def __consumer_handler(self, websocket_client_connection):
        if websocket_client_connection is None:
            return
        id = str(
            websocket_client_connection.request_headers.get_all("Origin")[0])
        log.warning("Consumer handler of %s starting" % str(id))
        while websocket_client_connection.open:
            message = None
            try:
                message = await asyncio.wait_for(websocket_client_connection.recv(), timeout=0.02)
            except asyncio.TimeoutError as te:
                await asyncio.sleep(0.02)
            except websockets.exceptions.ConnectionClosed as cc:
                log.warning(
                    "Connection to %s was closed, stopping worker" % str(id))
                self.__current_users_mutex.acquire()
                worker = self.__current_users.get(id, None)
                self.__current_users_mutex.release()
                if worker is not None:
                    # TODO: do it abruptly in the worker, maybe set a flag to be checked for in send_and_wait to
                    # TODO: throw an exception
                    worker[1].stop_worker()
                self.clean_up_user(id)
                return

            if message is not None:
                await self.__on_message(message)
        log.warning("Connection closed in consumer_handler")

    def clean_up_user(self, id):
        self.__current_users_mutex.acquire()
        if id in self.__current_users.keys():
            if self.__current_users[id][2].open:
                log.debug("Calling close for %s..." % str(id))
                asyncio.ensure_future(
                    self.__current_users[id][2].close(), loop=self.__loop)
            self.__current_users.pop(id)
        self.__current_users_mutex.release()

    async def __on_message(self, message):
        id = -1
        response = None
        if isinstance(message, str):
            log.debug("Receiving message: %s" % str(message))
            splitup = message.split(";")
            id = int(splitup[0])
            response = splitup[1]
        else:
            log.debug("Received binary values.")
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
            log.error("Request has already been deleted...")
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

    def send_and_wait(self, id, message, timeout):
        log.debug("%s sending command: %s" % (str(id), message))
        self.__current_users_mutex.acquire()
        user_entry = self.__current_users.get(id, None)
        self.__current_users_mutex.release()
        if user_entry is None:
            raise WebsocketWorkerRemovedException

        message_id = self.__get_new_message_id()
        message_event = Event()
        message_event.clear()

        self.__set_request(message_id, message_event)

        to_be_sent = u"%s;%s" % (str(message_id), message)
        log.debug("To be sent: %s" % to_be_sent)
        self.__send(id, to_be_sent)

        # now wait for the response!
        result = None
        log.debug("Timeout: %s" % str(timeout))
        if message_event.wait(timeout):
            log.debug("Received answer in time, popping response")
            self.__reset_fail_counter(id)
            result = self.__pop_response(message_id)
            log.debug("Response: %s" % str(result))
        else:
            # timeout reached
            log.warning("Timeout, increasing timeout-counter")
            # TODO: why is the user removed here?
            new_count = self.__increase_fail_counter(id)
            if new_count > 5:
                log.error("5 consecutive timeouts to %s, cleanup" % str(id))
                # TODO: signal worker to stop and NOT cleanup the websocket by itself!
                self.clean_up_user(id)
                raise WebsocketWorkerTimeoutException

        log.debug("Returning response to %s: %s" % (str(id), str(result)))
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
