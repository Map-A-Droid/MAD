import asyncio
import math
import time
from threading import Thread
from typing import Optional, Dict
import websockets
from mapadroid.utils.CustomTypes import MessageTyping
from mapadroid.utils.madGlobals import WebsocketWorkerRemovedException, WebsocketWorkerTimeoutException, \
    WebsocketWorkerConnectionClosedException
from mapadroid.worker.AbstractWorker import AbstractWorker
from mapadroid.utils.logging import get_logger, LoggerEnums, get_origin_logger


class ReceivedMessageEntry:
    def __init__(self):
        # TODO: consider timestamp of when the message was waited for to cleanup?
        self.message: Optional[MessageTyping] = None
        self.message_received_event: asyncio.Event = asyncio.Event()


class WebsocketConnectedClientEntry:
    def __init__(self, origin: str, worker_thread: Optional[Thread], worker_instance: Optional[AbstractWorker],
                 websocket_client_connection: Optional[websockets.WebSocketClientProtocol],
                 loop_running: asyncio.AbstractEventLoop):
        self.origin: str = origin
        self.worker_thread: Optional[Thread] = worker_thread
        self.worker_instance: Optional[AbstractWorker] = worker_instance
        self.websocket_client_connection: Optional[websockets.WebSocketClientProtocol] = websocket_client_connection
        self.loop_running: asyncio.AbstractEventLoop = loop_running
        self.fail_counter: int = 0
        self.received_messages: Dict[int, ReceivedMessageEntry] = {}
        self.received_mutex: asyncio.Lock = asyncio.Lock()
        self.message_id_counter: int = 0
        self.message_id_mutex: asyncio.Lock = asyncio.Lock()
        self.logger = get_origin_logger(get_logger(LoggerEnums.websocket), origin=origin)
        # store a timestamp in order to cleanup (soft-states)
        self.last_message_received_at: float = 0

    async def set_message_response(self, message_id: int, message: MessageTyping) -> None:
        async with self.received_mutex:
            message_entry = self.received_messages.get(message_id, None)
            if message_entry is not None:
                message_entry.message_received_event.set()
                message_entry.message = message
                self.last_message_received_at = time.time()

    def send_and_wait(self, message: MessageTyping, timeout: float, worker_instance: AbstractWorker,
                      byte_command: Optional[int] = None) -> Optional[MessageTyping]:
        future = asyncio.run_coroutine_threadsafe(
            self.send_and_wait_async(message, timeout, worker_instance, byte_command=byte_command),
            self.loop_running)
        return future.result()

    async def send_and_wait_async(self, message: MessageTyping, timeout: float, worker_instance: AbstractWorker,
                                  byte_command: Optional[int] = None) -> Optional[MessageTyping]:
        if self.worker_instance is None or self.worker_instance != worker_instance and worker_instance != 'madmin':
            # TODO: consider changing this...
            raise WebsocketWorkerRemovedException
        elif not self.websocket_client_connection.open:
            raise WebsocketWorkerConnectionClosedException

        # install new ReceivedMessageEntry
        message_id: int = await self.__get_new_message_id()
        new_entry = ReceivedMessageEntry()
        async with self.received_mutex:
            self.received_messages[message_id] = new_entry

        if isinstance(message, bytes):
            self.logger.debug("sending binary: {}", message[:10])
        else:
            self.logger.debug("sending command: {}", message.strip())
        # send message
        await self.__send_message(message_id, message, byte_command)

        # wait for it to trigger...
        self.logger.debug2("Timeout towards: {}", timeout)
        response = None
        try:
            event_triggered = await asyncio.wait_for(new_entry.message_received_event.wait(), timeout=timeout)
            if event_triggered:
                self.logger.debug("Received answer in time, popping response")
                self.fail_counter = 0
                if isinstance(new_entry.message, str):
                    self.logger.debug4("Response: {}", new_entry.message.strip())
                else:
                    self.logger.debug4("Received binary data , starting with {}", new_entry.message[:10])
                response = new_entry.message
        except asyncio.TimeoutError:
            self.logger.warning("Timeout, increasing timeout-counter")
            self.fail_counter += 1
            if self.fail_counter > 5:
                self.logger.error("5 consecutive timeouts or origin is not longer connected, cleanup")
                raise WebsocketWorkerTimeoutException
        finally:
            self.logger.debug2("Cleaning up received messaged.")
            async with self.received_mutex:
                self.received_messages.pop(message_id)
        self.logger.debug("Done sending command")
        return response

    async def __send_message(self, message_id: int, message: MessageTyping,
                             byte_command: Optional[int] = None) -> None:
        if isinstance(message, str):
            to_be_sent: str = u"%s;%s" % (str(message_id), message)
            self.logger.debug4("To be sent: {}", to_be_sent.strip())
        elif byte_command is not None:
            to_be_sent: bytes = (int(message_id)).to_bytes(4, byteorder='big')
            to_be_sent += (int(byte_command)).to_bytes(4, byteorder='big')
            to_be_sent += message
            self.logger.debug4("To be sent to (message ID: {}): {}", message_id, to_be_sent[:10])
        else:
            self.logger.error("Tried to send invalid message (bytes without byte command or no byte/str passed)")
            return
        await self.websocket_client_connection.send(to_be_sent)

    async def __get_new_message_id(self) -> int:
        async with self.message_id_mutex:
            self.message_id_counter += 1
            self.message_id_counter = int(math.fmod(self.message_id_counter, 100000))
            if self.message_id_counter == 100000:
                self.message_id_counter = 1
            new_message_id = self.message_id_counter
        return new_message_id
