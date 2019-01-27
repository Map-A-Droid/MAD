import queue
import asyncio
import sys

import websockets
import logging
import collections

from threading import Lock, Event, Thread

from utils.authHelper import check_auth
from utils.madGlobals import WebsocketWorkerRemovedException, MadGlobals
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

    def start_server(self):
        log.info("Starting websocket server...")
        loop = asyncio.new_event_loop()
        # build list of origin IDs
        allowed_origins = []
        for device in self.__device_mappings.keys():
            allowed_origins.append(device)

        log.info("Device mappings: %s" % str(self.__device_mappings))
        log.info("Allowed origins derived: %s" % str(allowed_origins))
        asyncio.set_event_loop(loop)
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
            websocket_client_connection.close()
            return

        consumer_task = asyncio.ensure_future(
            self._consumer_handler(websocket_client_connection, path))
        producer_task = asyncio.ensure_future(
            self._producer_handler(websocket_client_connection, path))
        done, pending = await asyncio.wait(
            [producer_task, consumer_task],
            return_when=asyncio.FIRST_COMPLETED,
        )
        log.info("consumer or producer of %s stopped, cancelling pending tasks"
                 % str(websocket_client_connection.request_headers.get_all("Origin")[0]))
        for task in pending:
            task.cancel()
        log.info("Awaiting unregister of %s" % str(websocket_client_connection.request_headers.get_all("Origin")[0]))
        await self.__unregister(websocket_client_connection)
        log.info("All done with %s" % str(websocket_client_connection.request_headers.get_all("Origin")[0]))

    async def __register(self, websocket_client_connection):
        log.info("Client %s registering" % str(websocket_client_connection.request_headers.get_all("Origin")[0]))
        try:
            id = str(websocket_client_connection.request_headers.get_all("Origin")[0])
        except IndexError:
            log.warning("Client from %s tried to connect without Origin header"
                        % str(websocket_client_connection.request_headers.get_all("Origin")[0]))
            return False

        if self.__auths:
            try:
                authBase64 = str(websocket_client_connection.request_headers.get_all("Authorization")[0])
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
        daytime_routemanager = self.__routemanagers[client_mapping["daytime_area"]].get("routemanager")
        if client_mapping.get("nighttime_area", None) is not None:
            nightime_routemanager = self.__routemanagers[client_mapping["nighttime_area"]].get("routemanager", None)
        else:
            nightime_routemanager = None
        devicesettings = client_mapping["settings"]

        started = False
        if MadGlobals.sleep is True:
            # start the appropriate nighttime manager if set
            if nightime_routemanager is None:
                pass
            elif nightime_routemanager.mode in ["raids_mitm", "mon_mitm", "iv_mitm"]:
                worker = WorkerMITM(self.args, id, last_known_state, self, daytime_routemanager, nightime_routemanager,
                                    self.__mitm_mapper, devicesettings, db_wrapper=self.__db_wrapper)
                started = True
            elif nightime_routemanager.mode in ["raids_ocr"]:
                from worker.WorkerOcr import WorkerOcr
                worker = WorkerOcr(self.args, id, last_known_state, self, daytime_routemanager, nightime_routemanager,
                                   devicesettings, db_wrapper=self.__db_wrapper)
                started = True
            elif nightime_routemanager.mode in ["pokestops"]:
                worker = WorkerQuests(self.args, id, last_known_state, self, daytime_routemanager, nightime_routemanager,
                                      self.__mitm_mapper, devicesettings, db_wrapper=self.__db_wrapper)
                started = True
            else:
                log.fatal("Mode not implemented")
                sys.exit(1)
        if not MadGlobals.sleep or not started:
            # we either gotta run daytime mode OR nighttime routemanager not set
            if daytime_routemanager.mode in ["raids_mitm", "mon_mitm", "iv_mitm"]:
                worker = WorkerMITM(self.args, id, last_known_state, self, daytime_routemanager, nightime_routemanager,
                                    self.__mitm_mapper, devicesettings, db_wrapper=self.__db_wrapper)
            elif daytime_routemanager.mode in ["raids_ocr"]:
                from worker.WorkerOcr import WorkerOcr
                worker = WorkerOcr(self.args, id, last_known_state, self, daytime_routemanager, nightime_routemanager,
                                   devicesettings, db_wrapper=self.__db_wrapper)
            elif daytime_routemanager.mode in ["pokestops"]:
                worker = WorkerQuests(self.args, id, last_known_state, self, daytime_routemanager, nightime_routemanager,
                                      self.__mitm_mapper, devicesettings, db_wrapper=self.__db_wrapper)
            else:
                log.fatal("Mode not implemented")
                sys.exit(1)

        new_worker_thread = Thread(name='worker_%s' % id, target=worker.start_worker)
        new_worker_thread.daemon = True
        self.__current_users_mutex.acquire()
        self.__current_users[id] = [new_worker_thread, worker, websocket_client_connection, 0]
        self.__current_users_mutex.release()
        new_worker_thread.start()

        return True

    async def __unregister(self, websocket_client_connection):
        id = str(websocket_client_connection.request_headers.get_all("Origin")[0])
        self.__current_users_mutex.acquire()
        worker = self.__current_users.get(id, None)
        if worker is not None:
            self.__current_users.pop(id)
        self.__current_users_mutex.release()

    async def __producer_handler(self):
        while True:
            # retrieve next message from queue to be sent, block if empty
            next = None
            while next is None:
                next = await self.__retrieve_next_send()
                await self.__send_specific(next.id, next.message)

    async def __send_specific(self, id, message):
        for key, value in self.__current_users.items():
            if key == id and value[2].open:
                await value[2].send(message)

    async def _retrieve_next_send(self):
        found = None
        while found is None:
            try:
                found = self.__send_queue.get_nowait()
            except Exception as e:
                log.error("Exception %s in retrieve_next_send" % str(e))
                await asyncio.sleep(0.02)
        return found

