import functools
import queue
import time
from threading import Thread, current_thread, Event
from typing import Dict, Optional, Set, Coroutine, List
import random as rand
import websockets
import asyncio
from mapadroid.db.DbWrapper import DbWrapper
from mapadroid.mitm_receiver.MitmMapper import MitmMapper
from mapadroid.ocr.pogoWindows import PogoWindows
from mapadroid.utils.CustomTypes import MessageTyping
from mapadroid.utils.MappingManager import MappingManager
from mapadroid.utils.authHelper import check_auth
from mapadroid.data_manager import DataManager
from mapadroid.utils.logging import InterceptHandler, get_logger, LoggerEnums, get_origin_logger
import logging
from mapadroid.websocket.AbstractCommunicator import AbstractCommunicator
from mapadroid.websocket.WebsocketConnectedClientEntry import WebsocketConnectedClientEntry
from mapadroid.websocket.communicator import Communicator
from mapadroid.worker.AbstractWorker import AbstractWorker
from mapadroid.worker.WorkerFactory import WorkerFactory

logging.getLogger('websockets.server').setLevel(logging.DEBUG)
logging.getLogger('websockets.protocol').setLevel(logging.DEBUG)
logging.getLogger('websockets.server').addHandler(InterceptHandler(log_section=LoggerEnums.websocket))
logging.getLogger('websockets.protocol').addHandler(InterceptHandler(log_section=LoggerEnums.websocket))


logger = get_logger(LoggerEnums.websocket)


class WebsocketServer(object):
    def __init__(self, args, mitm_mapper: MitmMapper, db_wrapper: DbWrapper, mapping_manager: MappingManager,
                 pogo_window_manager: PogoWindows, data_manager: DataManager, event, enable_configmode: bool = False):
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
        self.__current_users_mutex: Optional[asyncio.Lock] = None
        self.__users_connecting: Set[str] = set()
        self.__users_connecting_mutex: Optional[asyncio.Lock] = None

        self.__worker_factory: WorkerFactory = WorkerFactory(self.__args, self.__mapping_manager, self.__mitm_mapper,
                                                             self.__db_wrapper, self.__pogo_window_manager, event)

        # asyncio loop for the entire server
        self.__loop: Optional[asyncio.AbstractEventLoop] = asyncio.new_event_loop()
        self.__loop_tid: int = -1
        self.__worker_shutdown_queue: queue.Queue[Thread] = queue.Queue()
        self.__internal_worker_join_thread: Thread = Thread(name='system',
                                                            target=self.__internal_worker_join)
        self.__internal_worker_join_thread.daemon = True

    def _add_task_to_loop(self, coro: Coroutine):
        create_task = functools.partial(self.__loop.create_task, coro)
        if current_thread() == self.__loop_tid:
            # We can call directly if we're not going between threads.
            return create_task()
        else:
            # We're in a non-event loop thread so we use a Future
            # to get the task from the event loop thread once
            # it's ready.
            return self.__loop.call_soon_threadsafe(create_task)

    async def __setup_first_loop(self):
        self.__current_users_mutex: asyncio.Lock = asyncio.Lock()
        self.__users_connecting_mutex: asyncio.Lock = asyncio.Lock()

    def start_server(self) -> None:
        logger.info("Starting websocket-server...")

        logger.debug("Device mappings: {}", self.__mapping_manager.get_all_devicemappings())

        asyncio.set_event_loop(self.__loop)
        if not self.__internal_worker_join_thread.is_alive():
            self.__internal_worker_join_thread.start()
        self._add_task_to_loop(self.__setup_first_loop())
        # the type-check here is sorta wrong, not entirely sure why
        # noinspection PyTypeChecker
        self.__loop.run_until_complete(
            websockets.serve(self.__connection_handler, self.__args.ws_ip, int(self.__args.ws_port), max_size=2 ** 25,
                             close_timeout=10))
        self.__loop_tid = current_thread()
        self.__loop.run_forever()
        logger.info("Websocket-server stopping...")

    async def __close_all_connections_and_signal_stop(self):
        logger.info("Signaling all workers to stop")
        async with self.__current_users_mutex:
            for worker_entry in self.__current_users.values():
                worker_entry.worker_instance.stop_worker()
                await self.__close_websocket_client_connection(worker_entry.origin,
                                                               worker_entry.websocket_client_connection)
        logger.info("Done signalling all workers to stop")

    def stop_server(self) -> None:
        logger.info("Trying to stop websocket server")
        self.__stop_server.set()
        # wait for connecting users to empty
        while len(self.__users_connecting) > 0:
            logger.info("Shutdown of websocket waiting for connecting devices")
            time.sleep(1)

        future = asyncio.run_coroutine_threadsafe(
            self.__close_all_connections_and_signal_stop(),
            self.__loop)
        future.result()
        logger.info("Waiting for join-queue to be emptied and threads to be joined")
        if not self.__internal_worker_join_thread.is_alive():
            # join the join thread, gotta love the irony
            self.__internal_worker_join_thread.join()
        # TODO: this could block forever, should we just place a timeout and have daemon = True handle it all anyway?
        self.__worker_shutdown_queue.join()
        self.__loop.call_soon_threadsafe(self.__loop.stop)

        logger.info("Stopped websocket server")

    def __internal_worker_join(self):
        while not self.__stop_server.is_set() \
                or (self.__stop_server.is_set() and not self.__worker_shutdown_queue.empty()):
            try:
                next_item: Optional[Thread] = self.__worker_shutdown_queue.get_nowait()
            except queue.Empty:
                time.sleep(1)
                continue
            if next_item is not None:
                logger.info("Trying to join worker thread")
                try:
                    next_item.join(10)
                except RuntimeError as e:
                    logger.warning("Caught runtime error trying to join thread, the thread likely did not start at all."
                                   " Exact message: {}", e)
                if next_item.is_alive():
                    logger.debug("Error while joining worker thread - requeue it")
                    self.__worker_shutdown_queue.put(next_item)
                else:
                    logger.debug("Done with worker thread, moving on")
            self.__worker_shutdown_queue.task_done()
        logger.info("Worker join-thread done")

    @logger.catch()
    async def __connection_handler(self, websocket_client_connection: websockets.WebSocketClientProtocol,
                                   path: str) -> None:
        if self.__stop_server.is_set():
            return
        # check auth and stuff TODO
        origin: Optional[str]
        success: Optional[bool]
        (origin, success) = await self.__authenticate_connection(websocket_client_connection)
        if success is False:
            # failed auth, stop connection
            await self.__close_websocket_client_connection(origin, websocket_client_connection)
            return
        origin_logger = get_origin_logger(logger, origin=origin)
        origin_logger.info("New connection from {}", websocket_client_connection.remote_address)
        async with self.__users_connecting_mutex:
            if origin in self.__users_connecting:
                origin_logger.info("Client is already connecting")
                return
            else:
                self.__users_connecting.add(origin)

        continue_register = True
        async with self.__current_users_mutex:
            origin_logger.debug("Checking if an entry is already present")
            entry = self.__current_users.get(origin, None)
            if entry is None:
                origin_logger.info("Need to start a new worker thread")

                entry = WebsocketConnectedClientEntry(origin=origin,
                                                      websocket_client_connection=websocket_client_connection,
                                                      worker_instance=None,
                                                      worker_thread=None,
                                                      loop_running=self.__loop)
                if not await self.__add_worker_and_thread_to_entry(entry, origin):
                    continue_register = False
            else:
                origin_logger.info("There is a worker thread entry present, handling accordingly")
                if entry.websocket_client_connection.open:
                    origin_logger.error("Old connection open while a new one is attempted to be established, "
                                        "aborting handling of connection")
                    continue_register = False

                entry.websocket_client_connection = websocket_client_connection
                # TODO: also change the worker's Communicator? idk yet
                if entry.worker_thread.is_alive() and not entry.worker_instance.is_stopping():
                    origin_logger.info("Worker thread still alive, continue as usual")
                    # TODO: does this need more handling? probably update communicator or whatever?
                elif not entry.worker_thread.is_alive():
                    origin_logger.info("Old thread is dead, trying to start a new one")
                    if not await self.__add_worker_and_thread_to_entry(entry, origin):
                        continue_register = False
                else:
                    origin_logger.info("Old thread is about to stop. Wait a little and reconnect")
                    # random sleep to not have clients try again in sync
                    continue_register = False
            if continue_register:
                self.__current_users[origin] = entry

        if not continue_register:
            await asyncio.sleep(rand.uniform(3, 15))
            async with self.__users_connecting_mutex:
                origin_logger.debug("Removing from users_connecting")
                self.__users_connecting.remove(origin)
            return

        try:
            if not entry.worker_thread.is_alive():
                entry.worker_thread.start()
            # TODO: we need to somehow check threads and synchronize connection status with worker status?
            async with self.__users_connecting_mutex:
                self.__users_connecting.remove(origin)
            receiver_task = asyncio.ensure_future(
                self.__client_message_receiver(origin, entry))
            await receiver_task
        except Exception as e:
            origin_logger.opt(exception=True).error("Other unhandled exception during registration: {}", e)
        # also check if thread is already running to not start it again. If it is not alive, we need to create it..
        finally:
            origin_logger.info("Awaiting unregister")
            # TODO: cleanup thread is not really desired, I'd prefer to only restart a worker if the route changes :(
            self.__worker_shutdown_queue.put(entry.worker_thread)
        origin_logger.info("Done with connection ({})", websocket_client_connection.remote_address)

    async def __add_worker_and_thread_to_entry(self, entry, origin) -> bool:
        communicator: AbstractCommunicator = Communicator(
            entry, origin, None, self.__args.websocket_command_timeout)
        worker: Optional[AbstractWorker] = await self.__worker_factory \
            .get_worker_using_settings(origin, self.__enable_configmode,
                                       communicator=communicator)
        if worker is None:
            return False
        # to break circular dependencies, we need to set the worker ref >.<
        communicator.worker_instance_ref = worker
        new_worker_thread = Thread(name=origin, target=worker.start_worker)
        new_worker_thread.daemon = True
        entry.worker_thread = new_worker_thread
        entry.worker_instance = worker
        return True

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
            logger.warning("Client from {} tried to connect without Origin header",
                           websocket_client_connection.remote_address)
            return (None, False)
        origin_logger = get_origin_logger(logger, origin=origin)
        if not self.__data_manager.is_device_active(origin):
            origin_logger.warning('Origin is currently paused. Unpause through MADmin to begin working')
            return (origin, False)
        origin_logger.info("Client registering")
        if self.__mapping_manager is None:
            origin_logger.warning("No configuration has been defined.  Please define in MADmin and click "
                                  "'APPLY SETTINGS'")
            (origin, False)
        elif origin not in self.__mapping_manager.get_all_devicemappings().keys():
            if(self.__data_manager.search('device', params={'origin': origin})):
                origin_logger.warning("Device is created but not loaded.  Click 'APPLY SETTINGS' in MADmin to Update")
            else:
                origin_logger.warning("Register attempt of unknown origin.  Please create the device in MADmin and "
                                      " click 'APPLY SETTINGS'")
            return (origin, False)

        valid_auths = self.__mapping_manager.get_auths()
        auth_base64 = None
        if valid_auths:
            try:
                auth_base64 = str(
                    websocket_client_connection.request_headers.get_all("Authorization")[0])
            except IndexError:
                origin_logger.warning("Client tried to connect without auth header")
                return (origin, False)
        if valid_auths and auth_base64 and not check_auth(origin_logger, auth_base64, self.__args, valid_auths):
            return (origin, False)
        return (origin, True)

    async def __client_message_receiver(self, origin: str, client_entry: WebsocketConnectedClientEntry) -> None:
        if client_entry is None:
            return
        connection: websockets.WebSocketClientProtocol = client_entry.websocket_client_connection
        origin_logger = get_origin_logger(logger, origin=origin)
        origin_logger.info("Consumer handler starting")
        while connection.open:
            message = None
            try:
                message = await asyncio.wait_for(connection.recv(), timeout=4.0)
            except asyncio.TimeoutError:
                await asyncio.sleep(0.02)
            except websockets.exceptions.ConnectionClosed as cc:
                # TODO: cleanup needed here? better suited for the handler
                origin_logger.warning("Connection was closed, stopping receiver. Exception: {}", cc)
                entry: Optional[WebsocketConnectedClientEntry] = self.__current_users.get(origin, None)
                if entry is not None:
                    entry.worker_instance.stop_worker()
                return

            if message is not None:
                await self.__on_message(client_entry, message)
        origin_logger.warning("Connection closed in __client_message_receiver")
        entry: Optional[WebsocketConnectedClientEntry] = self.__current_users.get(origin, None)
        if entry is not None:
            entry.worker_instance.stop_worker()

    @staticmethod
    async def __on_message(client_entry: WebsocketConnectedClientEntry, message: MessageTyping) -> None:
        response: Optional[MessageTyping] = None
        if isinstance(message, str):
            client_entry.logger.debug5("Receiving message: {}", message.strip())
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
        origin_logger = get_origin_logger(logger, origin=origin_of_worker)
        origin_logger.info('Closing connections')
        await websocket_client_connection.close()
        origin_logger.info("Connection closed")

    async def get_connected_origins(self) -> List[str]:
        async with self.__current_users_mutex:
            origins_connected: List[str] = []
            for origin, entry in self.__current_users.items():
                if entry.websocket_client_connection.open:
                    origins_connected.append(origin)
            return origins_connected

    def get_reg_origins(self) -> List[str]:
        future = asyncio.run_coroutine_threadsafe(
            self.get_connected_origins(),
            self.__loop)
        return future.result()

    def get_origin_communicator(self, origin: str) -> Optional[AbstractCommunicator]:
        # TODO: this should probably lock?
        entry: Optional[WebsocketConnectedClientEntry] = self.__current_users.get(origin, None)
        return (entry.worker_instance.communicator
                if entry is not None and entry.worker_instance is not None
                else False)

    def set_geofix_sleeptime_worker(self, origin: str, sleeptime: int) -> bool:
        entry: Optional[WebsocketConnectedClientEntry] = self.__current_users.get(origin, None)
        return (entry.worker_instance.set_geofix_sleeptime(sleeptime)
                if entry is not None and entry.worker_instance is not None
                else False)

    def set_job_activated(self, origin) -> None:
        self.__mapping_manager.set_devicesetting_value_of(origin, 'job', True)

    def set_job_deactivated(self, origin) -> None:
        self.__mapping_manager.set_devicesetting_value_of(origin, 'job', False)

    async def __close_and_signal_stop(self, origin: str) -> None:
        origin_logger = get_origin_logger(logger, origin=origin)
        origin_logger.info("Signaling to stop")
        async with self.__current_users_mutex:
            entry: Optional[WebsocketConnectedClientEntry] = self.__current_users.get(origin, None)
            if entry is not None:
                entry.worker_instance.stop_worker()
                await self.__close_websocket_client_connection(entry.origin,
                                                               entry.websocket_client_connection)
                origin_logger.info("Done signaling stop")
            else:
                origin_logger.warning("Unable to signal to stop, not present")

    def force_disconnect(self, origin) -> None:
        future = asyncio.run_coroutine_threadsafe(
            self.__close_and_signal_stop(origin),
            self.__loop)
        future.result()
