import asyncio
import json
import logging
import websockets

logging.basicConfig()

STATE = {'value': 0}

USERS = set()

def state_event():
    print("Send account count")
    return 'account_count 1'

def send_account():
    print ("Send account")
    return '047s5z77O:Zn3_s6$W&mG8'

def users_event():
    return json.dumps({'type': 'users', 'count': len(USERS)})

async def notify_state():
    if USERS:       # asyncio.wait doesn't accept an empty list
        message = state_event()
        await asyncio.wait([user.send(message) for user in USERS])

async def notify_users():
    if USERS:       # asyncio.wait doesn't accept an empty list
        message = users_event()
        await asyncio.wait([user.send(message) for user in USERS])

async def register(websocket):
    print(websocket)
    USERS.add(websocket)
    await notify_users()

async def unregister(websocket):
    print(websocket)
    USERS.remove(websocket)
    await notify_users()

async def counter(websocket, path):
    # register(websocket) sends user_event() to websocket
    await register(websocket)
    try:
        await websocket.send(state_event())
        await websocket.send(send_account())
        async for message in websocket:
            print(message)
    finally:
        await unregister(websocket)

asyncio.get_event_loop().run_until_complete(
    websockets.serve(counter, '0.0.0.0', 8080))
asyncio.get_event_loop().run_forever()