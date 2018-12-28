import asyncio
import collections
import logging
import math
import queue
from abc import ABC
from threading import Lock, Event, Thread

import websockets

from utils.authHelper import check_auth
from utils.madGlobals import WebsocketWorkerRemovedException
from worker.WorkerMITM import WorkerMITM

log = logging.getLogger(__name__)
OutgoingMessage = collections.namedtuple('OutgoingMessage', ['id', 'message'])


class WebsocketServerBase(ABC):
    def __init__(self, args, listen_address, listen_port, received_mapping, db_wrapper, routemanagers, device_mappings,
                 auths):
        self.__current_users = {}
        self.__listen_adress = listen_address
        self.__listen_port = listen_port
        self._send_queue = queue.Queue()

        self.__received = {}  # map with received IDs
        self.__receivedMutex = Lock()

        self.__requests = {}  # map with ID, event mapping
        self.__requestsMutex = Lock()

        self.__nextId = 0
        self.__idMutex = Lock()
        self.args = args
        self.db_wrapper = db_wrapper
        self.device_mappings = device_mappings
        self.routemanagers = routemanagers
        self.auths = auths
        self._received_mapping = received_mapping

    def start_server(self):
        log.info("Starting websocket server...")
        loop = asyncio.new_event_loop()
        # build list of origin IDs
        allowed_origins = []
        for device in self.device_mappings.keys():
            allowed_origins.append(device)

        log.info("Device mappings: %s" % str(self.device_mappings))
        log.info("Allowed origins derived: %s" % str(allowed_origins))
        asyncio.set_event_loop(loop)
        asyncio.get_event_loop().run_until_complete(
            websockets.serve(self.handler, self.__listen_adress, self.__listen_port, max_size=2 ** 25,
                             origins=allowed_origins))
        asyncio.get_event_loop().run_forever()

    async def __unregister(self, websocket):
        id = str(websocket.request_headers.get_all("Origin")[0])
        worker = self.__current_users.get(id, None)
        if worker is None:
            return
        else:
            worker[1].stop_worker()
            self.__current_users.pop(id)

    async def __register(self, websocket):
        # await websocket.recv()
        log.info("Client registering....")
        try:
            id = str(websocket.request_headers.get_all("Origin")[0])
        except IndexError:
            log.warning("Client from %s tried to connect without Origin header" % str(websocket)) # TODO: list IP or whatever...
            return False
        if self.auths:
            try:
                authBase64 = str(websocket.request_headers.get_all("Authorization")[0])
            except IndexError:
                log.warning("Client from %s tried to connect without auth header" % str(websocket))
                return False
        if self.__current_users.get(id, None) is not None:
            log.warning("Worker for %s is already running" % str(id))
            return False
        elif self.auths and authBase64 and not check_auth(authBase64, self.args, self.auths):
            return False

        lastKnownState = {}
        client_mapping = self.device_mappings[id]
        daytime_routemanager = self.routemanagers[client_mapping["daytime_area"]].get("routemanager")
        if client_mapping.get("nighttime_area", None) is not None:
            nightime_routemanager = self.routemanagers[client_mapping["nighttime_area"]].get("routemanager", None)
        else:
            nightime_routemanager = None
        devicesettings = client_mapping["settings"]

        if daytime_routemanager.mode == "raids_mitm" or daytime_routemanager.mode == "mon_mitm":
            Worker = WorkerMITM(self.args, id, lastKnownState, self, daytime_routemanager, nightime_routemanager,
                                self._received_mapping, devicesettings, db_wrapper=self.db_wrapper)
        else:
            from worker.WorkerOcr import WorkerOcr
            Worker = WorkerOcr(self.args, id, lastKnownState, self, daytime_routemanager, nightime_routemanager,
                               devicesettings, db_wrapper=self.db_wrapper)
            # start off new thread, pass our instance in
        newWorkerThread = Thread(name='worker_%s' % id, target=Worker.start_worker)
        newWorkerThread.daemon = False
        newWorkerThread.start()
        self.__current_users[id] = [newWorkerThread, Worker, websocket]

        return True

    def __send(self, id, message):
        nextMessage = OutgoingMessage(id, message)
        self._send_queue.put(nextMessage)

    async def _retrieve_next_send(self):
        found = None
        while found is None:
            try:
                found = self._send_queue.get_nowait()
            except:
                await asyncio.sleep(0.02)
        return found
        # return self._send_queue.get(True)

    async def _producer_handler(self, websocket, path):
        while True:
            # retrieve next message from queue to be sent, block if empty
            next = None
            while next is None:
                next = await self._retrieve_next_send()
            # TODO: next consists of pair <id, message>, split that up and send message to the user with the ID
            await self.__send_specific(next.id, next.message)
            # message = await websocket.recv()
            # log.debug("Recv: %s" % str("Done"))
            # await asyncio.wait([value[1].send(next.message) for key, value in self.__current_users if key == next.id])
            # await websocket.send()

    async def __send_specific(self, id, message):
        for key, value in self.__current_users.items():
            if key == id and value[2].open:
                await value[2].send(message)

        # [value[1].send(next.message) for key, value in self.__current_users if key == next.id]

    async def _consumer_handler(self, websocket, path):
        while True:
            message = None
            id = str(websocket.request_headers.get_all("Origin")[0])
            try:
                asyncio.wait_for(websocket.recv(), timeout=0.01)
                message = await websocket.recv()
            except asyncio.TimeoutError:
                log.debug('timeout!')
                await asyncio.sleep(0.02)
            except websockets.exceptions.ConnectionClosed:
                log.debug("Connection closed while receiving data")
                log.debug("Closed connection to %s" % str(id))
                worker = self.__current_users.get(id, None)
                return
                # TODO: cleanup, stop worker...
            if message is not None:
                self.__onMessage(message)

    async def handler(self, websocket, path):
        log.debug("Waiting for connections")
        continueWork = await self.__register(websocket)
        # newWorkerThread = Thread(name='worker%s' % id, target=self._consumer_handler, args=(websocket, path,))
        # newWorkerThread.daemon = False
        # newWorkerThread.start()
        if not continueWork:
            return
        consumer_task = asyncio.ensure_future(
            self._consumer_handler(websocket, path))
        producer_task = asyncio.ensure_future(
            self._producer_handler(websocket, path))
        done, pending = await asyncio.wait(
            [producer_task, consumer_task],
            return_when=asyncio.FIRST_COMPLETED,
        )
        for task in pending:
            task.cancel()
        log.info("All done with %s" % str(websocket.request_headers.get_all("Origin")[0]))
        await self.__unregister(websocket)

    def __onMessage(self, message):
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
        self.__setResponse(id, response)
        if not self.__setEvent(id):
            # remove the response again - though that is kinda stupid
            self.__popResponse(id)

    def __getNewMessageId(self):
        self.__idMutex.acquire()
        self.__nextId += 1
        self.__nextId = int(math.fmod(self.__nextId, 100000))
        if self.__nextId == 100000:
            self.__nextId = 1
        toBeReturned = self.__nextId
        self.__idMutex.release()
        return toBeReturned

    def __setRequest(self, id, event):
        self.__requestsMutex.acquire()
        self.__requests[id] = event
        self.__requestsMutex.release()

    def __setEvent(self, id):
        self.__requestsMutex.acquire()
        result = False
        if id in self.__requests:
            self.__requests[id].set()
            result = True
        else:
            # the request has already been deleted due to a timeout...
            result = False
        self.__requestsMutex.release()
        return result

    def __removeRequest(self, id):
        self.__requestsMutex.acquire()
        self.__requests.pop(id)
        self.__requestsMutex.release()

    def __setResponse(self, id, message):
        self.__receivedMutex.acquire()
        self.__received[id] = message
        self.__receivedMutex.release()

    def __popResponse(self, id):
        self.__receivedMutex.acquire()
        message = self.__received.pop(id)
        self.__receivedMutex.release()
        return message

    def sendAndWait(self, id, message, timeout):
        log.debug("Sending command: %s" % message)
        if self.__current_users.get(id, None) is None:
            raise WebsocketWorkerRemovedException
        messageId = self.__getNewMessageId()
        messageEvent = Event()
        messageEvent.clear()

        self.__setRequest(messageId, messageEvent)

        toBeSent = u"%s;%s" % (str(messageId), message)
        log.debug("Sending:")
        log.debug("To be sent: %s" % toBeSent)

        self.__send(id, toBeSent)

        result = None
        log.debug("Timeout: " + str(timeout))
        if messageEvent.wait(timeout):
            log.debug("Received anser, popping response")
            log.debug("Received an answer")
            # okay, we can get the response..
            result = self.__popResponse(messageId)
            log.debug("Answer: %s" % result)
        else:
            # timeout reached
            log.warning("Timeout reached while waiting for a response...")
            if self.__current_users.get(id, None) is None:
                raise WebsocketWorkerRemovedException

        log.debug("Received response: %s" % str(result))
        self.__removeRequest(messageId)
        log.debug("Returning response to worker.")
        return result
