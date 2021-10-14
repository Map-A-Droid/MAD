import asyncio
import time
from typing import Optional

from aiohttp import web
from aiohttp.web_runner import TCPSite, UnixSite
from loguru import logger

from mapadroid.data_handler.mitm_data.AbstractMitmMapper import AbstractMitmMapper
from mapadroid.db.DbWrapper import DbWrapper
from mapadroid.mad_apk.abstract_apk_storage import AbstractAPKStorage
from mapadroid.mapping_manager import MappingManager
from mapadroid.mitm_receiver.endpoints import \
    register_mitm_receiver_root_endpoints
from mapadroid.mitm_receiver.endpoints.autoconfig import \
    register_autoconfig_endpoints
from mapadroid.mitm_receiver.endpoints.mad_apk import \
    register_mad_apk_endpoints


class MITMReceiver:
    def __init__(self, mitm_mapper: AbstractMitmMapper, args_passed, mapping_manager: MappingManager,
                 db_wrapper: DbWrapper, storage_obj: AbstractAPKStorage, data_queue: asyncio.Queue,
                 name=None, enable_configmode: Optional[bool] = False):
        self.__application_args = args_passed
        self.__mapping_manager: MappingManager = mapping_manager
        self.__mitm_mapper: AbstractMitmMapper = mitm_mapper
        self._db_wrapper: DbWrapper = db_wrapper
        self._data_queue: asyncio.Queue = data_queue
        self._storage_obj: AbstractAPKStorage = storage_obj
        self.app: Optional[web.Application] = None

        self.__mitmreceiver_startup_time: float = time.time()

    async def shutdown(self):
        logger.info("MITMReceiver stop called...")
        for _ in range(self.__application_args.mitmreceiver_data_workers):
            await self._data_queue.put(None)

    async def start(self) -> web.AppRunner:
        self.__mitmreceiver_startup_time: float = time.time()

        # ~20 MB max size
        client_max_size = (1024 ** 2) * 20
        self._app = web.Application(client_max_size=client_max_size)
        self._app['MAX_CONTENT_LENGTH'] = client_max_size
        self._app.secret_key = "8bc96865945be733f3973ba21d3c5949"
        self._app['SEND_FILE_MAX_AGE_DEFAULT'] = 0
        self._app['db_wrapper'] = self._db_wrapper
        self._app['mad_args'] = self.__application_args
        self._app['mapping_manager'] = self.__mapping_manager
        self._app["mitm_mapper"] = self.__mitm_mapper
        self._app["mitmreceiver_startup_time"] = self.__mitmreceiver_startup_time
        self._app["data_queue"] = self._data_queue
        self._app["storage_obj"] = self._storage_obj  # TODO

        register_autoconfig_endpoints(self._app)
        register_mitm_receiver_root_endpoints(self._app)
        register_mad_apk_endpoints(self._app)

        runner: web.AppRunner = web.AppRunner(self._app)
        await runner.setup()
        if self.__application_args.mitm_unix_socket:
            site: UnixSite = web.UnixSite(runner, self.__application_args.mitm_unix_socket)
            logger.info("MITMReceiver starting at {}", self.__application_args.mitm_unix_socket)
        else:
            site: TCPSite = web.TCPSite(runner, self.__application_args.mitmreceiver_ip, self.__application_args.mitmreceiver_port)
            logger.info(f'MITMReceiver starting at '
                        f'http://{self.__application_args.mitmreceiver_ip}:'
                        f'{self.__application_args.mitmreceiver_port}')
        await site.start()
        # TODO: Return runner and call     await runner.cleanup()
        logger.info('Finished madmin')
        return runner
