from typing import Optional

import grpc

from mapadroid.data_handler.MitmMapperClient import MitmMapperClient


class MitmMapperClientConnector:
    def __init__(self):
        self._channel: Optional[grpc.Channel] = None

    async def start(self):
        self._channel = await grpc.aio.insecure_channel('localhost:50051')

    async def close(self):
        self._channel.close()

    async def __aenter__(self) -> MitmMapperClient:
        if not self._channel:
            await self.start()
        return MitmMapperClient(self._channel)

    async def __aexit__(self, type_, value, traceback):
        pass

