#!/usr/bin/env python

# WS server example

import asyncio

import websockets


async def hello(websocket, path):
    while True:
        command = input("Enter command: ")

        await websocket.send(command)

        response = await websocket.recv()
        log.debug(f"< {response}")

    # greeting = f" {response}!"
    #
    # await websocket.send(greeting)
    # log.debug(f"> {greeting}")

start_server = websockets.serve(hello, '', 8080)

asyncio.get_event_loop().run_until_complete(start_server)
asyncio.get_event_loop().run_forever()