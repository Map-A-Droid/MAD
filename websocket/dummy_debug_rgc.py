#!/usr/bin/env python

# WS server example

import asyncio

import websockets
from aioconsole import ainput


async def hello(websocket, path):
    print("Client registered")
    while True:
        command = await ainput("Enter command: ")
        print("Sending: %s" % command)
        await websocket.send("1;" + command)
        print("Awaiting response")
        response = await websocket.recv()
        print(f"Response: {response}")

    # greeting = f" {response}!"
    #
    # await websocket.send(greeting)
    # log.debug(f"> {greeting}")

print("Initializing websocket server")
start_server = websockets.serve(hello, '0.0.0.0', 8080)

print("Starting to serve")
asyncio.get_event_loop().run_until_complete(start_server)
asyncio.get_event_loop().run_forever()
