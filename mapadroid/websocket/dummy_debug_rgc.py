#!/usr/bin/env python

# WS server example

import asyncio

import socket
import websockets
from aioconsole import ainput


async def hello(websocket, path):
    print("Client registered")
    while True:
        command = await ainput("Enter command: ")
        print("Sending: %s" % command)
        await websocket.send("1;" + command)
        print("Awaiting response")

        message = None
        while message is None:
            try:
                message = await asyncio.wait_for(websocket.recv(), timeout=2.0)
            except asyncio.TimeoutError:
                await asyncio.sleep(0.02)
            except websockets.exceptions.ConnectionClosed:
                break

        if message is not None:
            if isinstance(message, str):
                print("Receiving message: {}", str(message.strip()))
                splitup = message.split(";")
                id = int(splitup[0])
                response = splitup[1]
            else:
                print("Received binary values.")
                id = int.from_bytes(message[:4], byteorder='big', signed=False)  # noqa: F841
                response = message[4:]

            if isinstance(response, str):
                print("Response: {}".format(str(response.strip())))
            else:
                print("Received binary data starting with {}. Storing it.".format(str(response[:10])))
                with open("derp.jpg", "wb") as fh:
                    fh.write(response)


print("Initializing websocket server")
port = 8080
start_server = websockets.serve(hello, '0.0.0.0', port)

print("Starting to serve ws://%s:%s" % (socket.gethostbyname(socket.gethostname()), port))
asyncio.get_event_loop().run_until_complete(start_server)
asyncio.get_event_loop().run_forever()
