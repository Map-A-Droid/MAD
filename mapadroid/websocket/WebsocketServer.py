from threading import Thread, current_thread, Lock, Event
from typing import Dict, Optional, Set

import websockets
import asyncio

from mapadroid.db.DbWrapper import DbWrapper
from mapadroid.mitm_receiver.MitmMapper import MitmMapper
from mapadroid.ocr.pogoWindows import PogoWindows
from mapadroid.utils.CustomTypes import MessageTyping
from mapadroid.utils.MappingManager import MappingManager
from mapadroid.utils.authHelper import check_auth
from mapadroid.utils.data_manager import DataManager
from mapadroid.utils.logging import logger, InterceptHandler
import logging

from mapadroid.websocket.WebsocketConnectedClientEntry import WebsocketConnectedClientEntry
from mapadroid.worker.AbstractWorker import AbstractWorker
from mapadroid.worker.WorkerFactory import WorkerFactory

logging.getLogger('websockets.server').setLevel(logging.DEBUG)
logging.getLogger('websockets.protocol').setLevel(logging.DEBUG)
logging.getLogger('websockets.server').addHandler(InterceptHandler())
logging.getLogger('websockets.protocol').addHandler(InterceptHandler())


class WebsocketServer(object):
    def __init__(self, args, mitm_mapper: MitmMapper, db_wrapper: DbWrapper, mapping_manager: MappingManager,
                 pogo_window_manager: PogoWindows, data_manager: DataManager, enable_configmode: bool = False):
        self.__args = args
        self.__db_wrapper: DbWrapper = db_wrapper
        self.__mapping_manager: MappingManager = mapping_manager
        self.__pogo_window_manager: PogoWindows = pogo_window_manager
        self.__data_manager: DataManager = data_manager
        self.__mitm_mapper: MitmMapper = mitm_mapper
        self.__enable_configmode: bool = enable_configmode

        # Event to signal that the server is to be stopped. Used to not accept new connections for example
        self.__stop_server: Event = Event()

        # Dict keeping currently running connections and workers for management
        # Do think twice before plainly accessing, there's locks to be used
        self.__current_users: Dict[str, WebsocketConnectedClientEntry] = {}
        self.__current_users_mutex: asyncio.Lock = asyncio.Lock()
        self.__users_connecting: Set[str] = set()
        self.__users_connecting_mutex: asyncio.Lock = asyncio.Lock()

        self.__worker_factory: WorkerFactory = WorkerFactory(self.__args, self.__mapping_manager, self.__mitm_mapper,
                                                             self.__db_wrapper, self.__pogo_window_manager)

        # asyncio loop for the entire server
        self.__loop: asyncio.AbstractEventLoop = asyncio.new_event_loop()
        self.__loop_tid: int = -1
        self.__loop_mutex = Lock()

    def start_server(self) -> None:
        logger.info("Starting websocket-server...")
        logger.debug("Device mappings: {}", str(self.__mapping_manager.get_all_devicemappings()))

        asyncio.set_event_loop(self.__loop)
        # the type-check here is sorta wrong, not entirely sure why
        # noinspection PyTypeChecker
        self.__loop.run_until_complete(
            websockets.serve(self.__connection_handler, self.__args.ws_ip, int(self.__args.ws_port), max_size=2 ** 25,
                             close_timeout=10))
        self.__loop_tid = current_thread()
        self.__loop.run_forever()
        logger.info("Websocket-server stopping...")

    async def __connection_handler(self, websocket_client_connection: websockets.WebSocketClientProtocol, path: str) \
            -> None:
        if self.__stop_server.is_set():
            await self.__close_websocket_client_connection("stopping...", websocket_client_connection)
            return
        # check auth and stuff TODO
        origin: Optional[str] = await self.__authenticate_connection(websocket_client_connection)
        if origin is None:
            # failed auth, stop connection
            await self.__close_websocket_client_connection("Stopping due to failed auth...",
                                                           websocket_client_connection)
            return

        async with self.__users_connecting_mutex:
            if origin in self.__users_connecting:
                logger.info("Client {} is already connecting".format(origin))
                return
            else:
                self.__users_connecting.add(origin)
        # check if the origin is already handed to an instance and just switch the connection if the thread is still
        # running
        async with self.__current_users_mutex:
            entry = self.__current_users.get(origin, None)
            if entry is None:
                logger.info("Need to start a new worker thread for {}", origin)

                entry = WebsocketConnectedClientEntry(origin=origin,
                                                      websocket_client_connection=websocket_client_connection,
                                                      worker_instance=None,
                                                      worker_thread=None,
                                                      loop_running=self.__loop)
                worker: Optional[AbstractWorker] = await self.__worker_factory \
                    .get_worker_using_settings(origin, self.__enable_configmode, websocket_client_entry=entry)
                if worker is None:
                    return
                new_worker_thread = Thread(
                    name='worker_%s' % origin, target=worker.start_worker)

                new_worker_thread.daemon = True
                entry.worker_thread = new_worker_thread
                entry.worker_instance = worker
            else:
                logger.info("There is a worker thread entry present, handling accordingly")
                if entry.websocket_client_connection.open:
                    logger.error("Old connection open while a new one is attempted to be established, "
                                 "aborting handling")
                    async with self.__users_connecting_mutex:
                        self.__users_connecting.remove(origin)
                    return

                entry.websocket_client_connection = websocket_client_connection
                # TODO: also change the worker's Communicator? idk yet
                if entry.worker_thread.is_alive():
                    logger.info("Worker thread still alive, continue as usual")
                    # TODO: does this need more handling? probably update communicator or whatever?
                else:
                    worker: Optional[AbstractWorker] = await self.__worker_factory \
                        .get_worker_using_settings(origin, self.__enable_configmode, entry)
                    if worker is None:
                        # TODO: handle properly
                        return
                    new_worker_thread = Thread(
                        name='worker_%s' % origin, target=worker.start_worker)

                    new_worker_thread.daemon = True
                    entry.worker_instance = worker
                    entry.worker_thread = new_worker_thread

            self.__current_users[origin] = entry
        try:
            if not entry.worker_thread.is_alive():
                entry.worker_thread.start()
            async with self.__users_connecting_mutex:
                self.__users_connecting.remove(origin)
            receiver_task = asyncio.ensure_future(
                self.__client_message_receiver(origin, entry))
            await receiver_task
        # also check if thread is already running to not start it again. If it is not alive, we need to create it..
        finally:
            logger.info("Awaiting unregister of {}", str(
                websocket_client_connection.request_headers.get_all("Origin")[0]))
            # await self.__unregister(websocket_client_connection)
            # logger.info("All done with {}", str(
            #    websocket_client_connection.request_headers.get_all("Origin")[0]))
            # TODO: cleanup thread is not really desired, I'd prefer to only restart a worker if the route changes :(
            # entry.worker_thread.join() is blocking the entire loop, do not do that! We need to tidy stuff up elsewhere
            while entry.worker_thread.is_alive():
                await asyncio.sleep(1)
                if not entry.worker_thread.is_alive():
                    entry.worker_thread.join()
        logger.info("Done with connection from {} ({})", origin, websocket_client_connection.remote_address)

    async def __get_new_worker(self, origin: str):
        # fetch worker from factory...
        # TODO: determine which to use....
        pass

    async def __authenticate_connection(self, websocket_client_connection: websockets.WebSocketClientProtocol) \
            -> Optional[str]:
        """
        :param websocket_client_connection:
        :return: origin (string) if the auth and everything else checks out, else None to signal abort
        """
        try:
            origin = str(
                websocket_client_connection.request_headers.get_all("Origin")[0])
        except IndexError:
            logger.warning("Client from {} tried to connect without Origin header", str(
                websocket_client_connection.request_headers.get_all("Origin")[0]))
            return None

        if not self.__data_manager.is_device_active(origin):
            logger.warning('Origin %s is currently paused.  Unpause through MADmin to begin working', origin)
            return None
        logger.info("Client {} registering", str(origin))
        if self.__mapping_manager is None or origin not in self.__mapping_manager.get_all_devicemappings().keys():
            logger.warning("Register attempt of unknown origin: {}. "
                           "Have you forgot to hit 'APPLY SETTINGS' in MADmin?".format(origin))
            return None

        valid_auths = self.__mapping_manager.get_auths()
        auth_base64 = None
        if valid_auths:
            try:
                auth_base64 = str(
                    websocket_client_connection.request_headers.get_all("Authorization")[0])
            except IndexError:
                logger.warning("Client from {} tried to connect without auth header", str(
                    websocket_client_connection.request_headers.get_all("Origin")[0]))
                return None
        if valid_auths and auth_base64 and not check_auth(auth_base64, self.__args, valid_auths):
            logger.warning("Invalid auth details received from {}", str(
                websocket_client_connection.request_headers.get_all("Origin")[0]))
            return None
        return origin

    async def __client_message_receiver(self, origin: str, client_entry: WebsocketConnectedClientEntry) -> None:
        if client_entry is None:
            return
        logger.info("Consumer handler of {} starting", origin)
        while client_entry.websocket_client_connection.open:
            message = None
            try:
                message = await asyncio.wait_for(client_entry.websocket_client_connection.recv(), timeout=4.0)
            except asyncio.TimeoutError:
                await asyncio.sleep(0.02)
            except websockets.exceptions.ConnectionClosed as cc:
                # TODO: cleanup needed here? better suited for the handler
                logger.warning(
                    "Connection to {} was closed, stopping receiver. Exception: ", origin, cc)
                return

            if message is not None:
                await self.__on_message(client_entry, message)
        logger.warning(
            "Connection of {} closed in __client_message_receiver", str(origin))

    @staticmethod
    async def __on_message(client_entry: WebsocketConnectedClientEntry, message: MessageTyping) -> None:
        response: Optional[MessageTyping] = None
        if isinstance(message, str):
            logger.debug("Receiving message: {}", str(message.strip()))
            splitup = message.split(";", 1)
            message_id = int(splitup[0])
            response = splitup[1]
        else:
            logger.debug("Received binary values.")
            message_id = int.from_bytes(message[:4], byteorder='big', signed=False)
            response = message[4:]
        await client_entry.set_message_response(message_id, response)

    @staticmethod
    async def __close_websocket_client_connection(origin_of_worker: str,
                                                  websocket_client_connection: websockets.WebSocketClientProtocol) \
            -> None:
        logger.info('Closing connections to device {}.', origin_of_worker)
        await websocket_client_connection.close()
        logger.info("Connection to device {} closed", origin_of_worker)

