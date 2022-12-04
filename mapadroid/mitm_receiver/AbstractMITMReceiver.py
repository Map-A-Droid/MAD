import asyncio
import time
from abc import ABC
from typing import Optional

from aiohttp import web

from mapadroid.data_handler.mitm_data.AbstractMitmMapper import \
    AbstractMitmMapper
from mapadroid.db.DbWrapper import DbWrapper
from mapadroid.mad_apk.abstract_apk_storage import AbstractAPKStorage
from mapadroid.mapping_manager import MappingManager


class MITMReceiver(ABC):
    _mapping_manager: MappingManager
    _mitm_mapper: AbstractMitmMapper
    _db_wrapper: DbWrapper
    _data_queue: asyncio.Queue
    _storage_obj: AbstractAPKStorage
    _app: web.Application
    _mitmreceiver_startup_time: float

    def __init__(self, mitm_mapper: AbstractMitmMapper, mapping_manager: MappingManager,
                 db_wrapper: DbWrapper, storage_obj: AbstractAPKStorage, data_queue: asyncio.Queue):
        self.__mapping_manager: MappingManager = mapping_manager
        self.__mitm_mapper: AbstractMitmMapper = mitm_mapper
        self._db_wrapper: DbWrapper = db_wrapper
        self._data_queue: asyncio.Queue = data_queue
        self._storage_obj: AbstractAPKStorage = storage_obj
        self._app: Optional[web.Application] = None

        self.__mitmreceiver_startup_time: float = time.time()
