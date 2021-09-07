from typing import Optional

import grpc

from mapadroid.mapping_manager.MappingManagerClient import MappingManagerClient


class MappingManagerClientConnector:
    def __init__(self):
        self._channel: Optional[grpc.Channel] = None

    async def start(self):
        max_message_length = 100 * 1024 * 1024
        options = [('grpc.max_message_length', max_message_length),
                   ('grpc.max_receive_message_length', max_message_length)]
        self._channel = grpc.aio.insecure_channel('localhost:50052', options=options)

    async def get_client(self) -> MappingManagerClient:
        if not self._channel:
            await self.start()
        return MappingManagerClient(self._channel)

    async def close(self):
        self._channel.close()

    async def __aenter__(self) -> MappingManagerClient:
        if not self._channel:
            await self.start()
        return MappingManagerClient(self._channel)

    async def __aexit__(self, type_, value, traceback):
        pass

