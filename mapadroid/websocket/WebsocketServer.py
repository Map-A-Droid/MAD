import asyncio
import logging
import queue
import random as rand
from asyncio import Task
from threading import current_thread
from typing import Dict, List, Optional, Set, Tuple

import websockets

from mapadroid.db.DbWrapper import DbWrapper
from mapadroid.db.helper.SettingsDeviceHelper import SettingsDeviceHelper
from mapadroid.db.model import SettingsDevice
from mapadroid.mapping_manager.MappingManager import MappingManager
from mapadroid.mapping_manager.MappingManagerDevicemappingKey import MappingManagerDevicemappingKey
from mapadroid.mitm_receiver.MitmMapper import MitmMapper
from mapadroid.ocr.pogoWindows import PogoWindows
from mapadroid.utils.CustomTypes import MessageTyping
from mapadroid.utils.authHelper import check_auth
from mapadroid.utils.logging import (InterceptHandler, LoggerEnums, get_logger,
                                     get_origin_logger)
from mapadroid.websocket.AbstractCommunicator import AbstractCommunicator
from mapadroid.websocket.WebsocketConnectedClientEntry import \
    WebsocketConnectedClientEntry
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
                 pogo_window_manager: PogoWindows, event, enable_configmode: bool = False):
        self.__args = args
        self.__db_wrapper: DbWrapper = db_wrapper
        self.__mapping_manager: MappingManager = mapping_manager
        self.__pogo_window_manager: PogoWindows = pogo_window_manager
        self.__mitm_mapper: MitmMapper = mitm_mapper
        self.__enable_configmode: bool = enable_configmode

        # Event to signal that the server is to be stopped. Used to not accept new connections for example
        self.__stop_server: asyncio.Event = asyncio.Event()

        # Dict keeping currently running connections and workers for management
        # Do think twice before plainly accessing, there's locks to be used
        self.__current_users: Dict[str, WebsocketConnectedClientEntry] = {}
        self.__current_users_mutex: Optional[asyncio.Lock] = None
        self.__users_connecting: Set[str] = set()
        self.__users_connecting_mutex: Optional[asyncio.Lock] = None

        self.__worker_factory: WorkerFactory = WorkerFactory(self.__args, self.__mapping_manager, self.__mitm_mapper,
                                                             self.__db_wrapper, self.__pogo_window_manager, event)

        # asyncio loop for the entire server
        self.__loop: Optional[asyncio.AbstractEventLoop] = None
        self.__loop_tid: int = -1
        self.__server_task = None
        self.__worker_shutdown_queue: asyncio.Queue[Task] = asyncio.Queue()
        self.__internal_worker_join_task: Optional[Task] = None

    async def __setup_first_loop(self):
        logger.debug("Device mappings: {}", await self.__mapping_manager.get_all_devicemappings())

        self.__current_users_mutex: asyncio.Lock = asyncio.Lock()
        self.__users_connecting_mutex: asyncio.Lock = asyncio.Lock()

    async def start_server(self) -> None:
        logger.info("Starting websocket-server...")

        self.__loop = asyncio.get_event_loop()
        self.__internal_worker_join_task: Task = self.__loop.create_task(self.__internal_worker_join())

        await self.__setup_first_loop()
        # the type-check here is sorta wrong, not entirely sure why
        # noinspection PyTypeChecker
        await websockets.serve(self.__connection_handler, self.__args.ws_ip, int(self.__args.ws_port), max_size=2 ** 25,
                               close_timeout=10)
        self.__loop_tid = current_thread()
        # self.__loop.run_forever()
        logger.info("Websocket-server stopping...")

    async def __close_all_connections_and_signal_stop(self):
        logger.info("Signaling all workers to stop")
        async with self.__current_users_mutex:
            for worker_entry in self.__current_users.values():
                await worker_entry.worker_instance.stop_worker()
                await self.__close_websocket_client_connection(worker_entry.origin,
                                                               worker_entry.websocket_client_connection)
        logger.info("Done signalling all workers to stop")

    async def stop_server(self) -> None:
        logger.info("Trying to stop websocket server")
        self.__stop_server.set()
        # wait for connecting users to empty
        while len(self.__users_connecting) > 0:
            logger.info("Shutdown of websocket waiting for connecting devices")
            await asyncio.sleep(1)

        await self.__close_all_connections_and_signal_stop()
        logger.info("Waiting for join-queue to be emptied and threads to be joined")
        # if not self.__internal_worker_join_task.done():
        # join the join thread, gotta love the irony
        # TODO: this is async..
        # await self.__internal_worker_join_task.join()
        #    self.__internal_worker_join_task.result()
        # TODO: this could block forever, should we just place a timeout and have daemon = True handle it all anyway?
        await self.__worker_shutdown_queue.join()
        # await self.__loop.stop)

        logger.info("Stopped websocket server")

    # TODO:.. is this really needed at all?
    async def __internal_worker_join(self):
        while not self.__stop_server.is_set() \
                or (self.__stop_server.is_set() and not self.__worker_shutdown_queue.empty()):
            try:
                next_item: Optional[Task] = self.__worker_shutdown_queue.get_nowait()
            except queue.Empty:
                await asyncio.sleep(1)
                continue
            if next_item is not None:
                logger.info("Trying to join worker thread")
                try:
                    await asyncio.wait_for(next_item, timeout=30)
                except asyncio.TimeoutError:
                    next_item.cancel()
                except RuntimeError as e:
                    logger.warning("Caught runtime error trying to join thread, the thread likely did not start at all."
                                   " Exact message: {}", e)
                # if next_item.is_alive():
                #    logger.debug("Error while joining worker thread - requeue it")
                #    self.__worker_shutdown_queue.put(next_item)
                # else:
                #    logger.debug("Done with worker thread, moving on")
            self.__worker_shutdown_queue.task_done()
        logger.info("Worker join-thread done")

    @logger.catch()
    async def __connection_handler(self, websocket_client_connection: websockets.WebSocketClientProtocol,
                                   path: str) -> None:
        """
        In case a new connection is being established, this method is called.
        Consequently, we are trying to create a worker that should live for as long as the connection is alive.
        Args:
            websocket_client_connection:
            path:

        Returns:

        """
        if self.__stop_server.is_set():
            return
        # check auth and stuff TODO
        origin: Optional[str]
        success: Optional[bool]
        (origin, success) = await self.__authenticate_connection(websocket_client_connection)
        if not success:
            # failed auth, stop connection
            await self.__close_websocket_client_connection(origin, websocket_client_connection)
            # TODO: Ensure the close is even needed here?
            return
        origin_logger = get_origin_logger(logger, origin=origin)
        origin_logger.info("New connection from {}", websocket_client_connection.remote_address)
        if self.__enable_configmode:
            origin_logger.warning('Connected in ConfigMode.  No mapping will occur in the current mode')
        async with self.__users_connecting_mutex:
            if origin in self.__users_connecting:
                origin_logger.info("Client is already connecting")
                return
            else:
                self.__users_connecting.add(origin)
        try:
            continue_register = True
            async with self.__current_users_mutex:
                origin_logger.debug("Checking if an entry is already present")
                entry = self.__current_users.get(origin, None)
                device: Optional[SettingsDevice] = None
                use_configmode = self.__enable_configmode
                if not self.__enable_configmode:
                    async with self.__db_wrapper as session, session:
                        device = await SettingsDeviceHelper.get_by_origin(session, self.__db_wrapper.get_instance_id(),
                                                                          origin)
                    if not await self.__mapping_manager.is_device_active(device.device_id):
                        origin_logger.warning('Origin is currently paused. Unpause through MADmin to begin working')
                        use_configmode = True
                if entry is None or use_configmode:
                    origin_logger.info("Need to start a new worker thread")

                    entry = WebsocketConnectedClientEntry(origin=origin,
                                                          websocket_client_connection=websocket_client_connection,
                                                          worker_instance=None,
                                                          worker_task=None)
                    if not await self.__add_worker_and_thread_to_entry(entry, origin, use_configmode=use_configmode):
                        continue_register = False
                else:
                    origin_logger.info("There is a worker thread entry present, handling accordingly")
                    if entry.websocket_client_connection.open:
                        origin_logger.error("Old connection open while a new one is attempted to be established, "
                                            "aborting handling of connection")
                        continue_register = False

                    entry.websocket_client_connection = websocket_client_connection
                    # TODO: also change the worker's Communicator? idk yet
                    if entry.worker_task and not entry.worker_task.done() and not entry.worker_instance.is_stopping():
                        origin_logger.info("Worker thread still alive, continue as usual")
                        # TODO: does this need more handling? probably update communicator or whatever?
                    # TODO: This check will not work with asyncio anymore...
                    elif entry.worker_task and not entry.worker_task.done():
                        origin_logger.info("Old task is not done but was supposed to stop?! Trying to start a new one")
                        # TODO: entry.worker_task.cancel() or somehow call cleanup&cancel?
                        #  entry.worker_task.cancel()
                        if not await self.__add_worker_and_thread_to_entry(entry, origin, use_configmode=use_configmode):
                            continue_register = False
                    else:
                        origin_logger.info("Old thread is about to stop. Wait a little and reconnect")
                        # random sleep to not have clients try again in sync
                        continue_register = False
                if continue_register:
                    self.__current_users[origin] = entry

            if not continue_register:
                await asyncio.sleep(rand.uniform(3, 15))
                return

            try:
                if entry.worker_task and not entry.worker_task.done():
                    # TODO..
                    pass
                # TODO: we need to somehow check threads and synchronize connection status with worker status?
                receiver_task = asyncio.ensure_future(
                    self.__client_message_receiver(origin, entry))
                await receiver_task
            except Exception as e:
                origin_logger.opt(exception=True).error("Other unhandled exception during registration: {}", e)
            # also check if thread is already running to not start it again. If it is not alive, we need to create it..
            finally:
                origin_logger.info("Awaiting unregister")
                # TODO: cleanup thread is not really desired, I'd prefer to only restart a worker if the route changes :(
                await self.__worker_shutdown_queue.put(entry.worker_task)
        finally:
            async with self.__users_connecting_mutex:
                self.__users_connecting.remove(origin)
        origin_logger.info("Done with connection ({})", websocket_client_connection.remote_address)

    async def __add_worker_and_thread_to_entry(self, entry, origin, use_configmode: bool = None) -> bool:
        communicator: AbstractCommunicator = Communicator(
            entry, origin, None, self.__args.websocket_command_timeout)
        use_configmode: bool = use_configmode if use_configmode is not None else self.__enable_configmode
        worker: Optional[AbstractWorker] = await self.__worker_factory \
            .get_worker_using_settings(origin, use_configmode, communicator=communicator)
        if worker is None:
            return False
        # to break circular dependencies, we need to set the worker ref >.<
        communicator.worker_instance_ref = worker
        entry.worker_task = await worker.start_worker()
        entry.worker_instance = worker
        return True

    async def __authenticate_connection(self, websocket_client_connection: websockets.WebSocketClientProtocol) \
            -> Tuple[Optional[str], bool]:
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
            return None, False
        origin_logger = get_origin_logger(logger, origin=origin)
        origin_logger.info("Client registering")
        if self.__mapping_manager is None:
            origin_logger.warning("No configuration has been defined.  Please define in MADmin and click "
                                  "'APPLY SETTINGS'")
            return origin, False
        elif origin not in (await self.__mapping_manager.get_all_devicemappings()).keys():
            async with self.__db_wrapper as session, session:
                device = await SettingsDeviceHelper.get_by_origin(session, self.__db_wrapper.get_instance_id(), origin)
            if device:
                origin_logger.warning("Device is created but not loaded.  Click 'APPLY SETTINGS' in MADmin to Update")
            else:
                origin_logger.warning("Register attempt of unknown origin.  Please create the device in MADmin and "
                                      " click 'APPLY SETTINGS'")
            return origin, False

        valid_auths = await self.__mapping_manager.get_auths()
        auth_base64 = None
        if valid_auths:
            try:
                auth_base64 = str(
                    websocket_client_connection.request_headers.get_all("Authorization")[0])
            except IndexError:
                origin_logger.warning("Client tried to connect without auth header")
                return origin, False
        if valid_auths and auth_base64 and not check_auth(origin_logger, auth_base64, self.__args, valid_auths):
            return origin, False
        return origin, True

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
                    await entry.worker_instance.stop_worker()
                return

            if message is not None:
                await self.__on_message(client_entry, message)
        origin_logger.warning("Connection closed in __client_message_receiver")
        entry: Optional[WebsocketConnectedClientEntry] = self.__current_users.get(origin, None)
        if entry is not None:
            await entry.worker_instance.stop_worker()

    @staticmethod
    async def __on_message(client_entry: WebsocketConnectedClientEntry, message: MessageTyping) -> None:
        response: Optional[MessageTyping] = None
        if isinstance(message, str):
            client_entry.logger.debug("Receiving message: {}", message.strip())
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

    async def get_reg_origins(self) -> List[str]:
        return await self.get_connected_origins()

    def get_origin_communicator(self, origin: str) -> Optional[AbstractCommunicator]:
        # TODO: this should probably lock?
        entry: Optional[WebsocketConnectedClientEntry] = self.__current_users.get(origin, None)
        return (entry.worker_instance.communicator
                if entry is not None and entry.worker_instance is not None
                else None)

    def set_geofix_sleeptime_worker(self, origin: str, sleeptime: int) -> bool:
        entry: Optional[WebsocketConnectedClientEntry] = self.__current_users.get(origin, None)
        return (entry.worker_instance.set_geofix_sleeptime(sleeptime)
                if entry is not None and entry.worker_instance is not None
                else False)

    async def set_job_activated(self, origin) -> None:
        await self.__mapping_manager.set_devicesetting_value_of(origin, MappingManagerDevicemappingKey.JOB_ACTIVE, True)

    async def set_job_deactivated(self, origin) -> None:
        await self.__mapping_manager.set_devicesetting_value_of(origin, MappingManagerDevicemappingKey.JOB_ACTIVE, False)

    async def __close_and_signal_stop(self, origin: str) -> None:
        origin_logger = get_origin_logger(logger, origin=origin)
        origin_logger.info("Signaling to stop")
        async with self.__current_users_mutex:
            entry: Optional[WebsocketConnectedClientEntry] = self.__current_users.get(origin, None)
            if entry is not None:
                await entry.worker_instance.stop_worker()
                await self.__close_websocket_client_connection(entry.origin,
                                                               entry.websocket_client_connection)
                origin_logger.info("Done signaling stop")
            else:
                origin_logger.warning("Unable to signal to stop, not present")

    async def force_disconnect(self, origin) -> None:
        await self.__close_and_signal_stop(origin)
