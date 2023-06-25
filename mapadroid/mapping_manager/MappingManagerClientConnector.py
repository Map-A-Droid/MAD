from typing import Optional

import grpc
from grpc._cython.cygrpc import CompressionAlgorithm, CompressionLevel

from mapadroid.mapping_manager.MappingManagerClient import MappingManagerClient
from mapadroid.utils.logging import LoggerEnums, get_logger
from mapadroid.utils.madGlobals import MadGlobals

logger = get_logger(LoggerEnums.mapping_manager)


class MappingManagerClientConnector:
    def __init__(self):
        self._channel: Optional[grpc.Channel] = None

    async def start(self):
        max_message_length = 100 * 1024 * 1024
        options = [('grpc.max_message_length', max_message_length),
                   ('grpc.max_receive_message_length', max_message_length)]
        if MadGlobals.application_args.mappingmanager_compression:
            options.extend([('grpc.default_compression_algorithm', CompressionAlgorithm.gzip),
                            ('grpc.grpc.default_compression_level', CompressionLevel.medium)])
        address = f'{MadGlobals.application_args.mappingmanager_ip}:{MadGlobals.application_args.mappingmanager_port}'
        if MadGlobals.application_args.mappingmanager_tls_cert_file:
            await self.__setup_secure_channel(address, options)
        else:
            await self.__setup_insecure_channel(address, options)

    async def __setup_insecure_channel(self, address, options):
        logger.warning("Insecure MitmMapper gRPC API client")
        self._channel = grpc.aio.insecure_channel(address, options=options)

    async def __setup_secure_channel(self, address, options):
        with open(MadGlobals.application_args.mappingmanager_tls_cert_file, 'r') as certfile:
            cert = certfile.read()
        credentials = grpc.ssl_channel_credentials(cert)
        self._channel = grpc.aio.secure_channel(address, credentials=credentials, options=options)

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
