import asyncio
from typing import Optional, NamedTuple

from mapadroid.db.DbWrapper import DbWrapper
from mapadroid.mitm_receiver.MitmMapper import MitmMapper
from mapadroid.ocr.pogoWindows import PogoWindows
from mapadroid.utils.MappingManager import MappingManager
from mapadroid.utils.collections import Location
from mapadroid.utils.madGlobals import WrongAreaInWalker
from mapadroid.utils.routeutil import pre_check_value
from mapadroid.websocket.AbstractCommunicator import AbstractCommunicator
from mapadroid.worker.AbstractWorker import AbstractWorker
from mapadroid.worker.WorkerConfigmode import WorkerConfigmode
from mapadroid.worker.WorkerMITM import WorkerMITM
from mapadroid.worker.WorkerQuests import WorkerQuests
from mapadroid.worker.WorkerType import WorkerType
from mapadroid.utils.logging import logger


class WalkerConfiguration(NamedTuple):
    walker_settings: dict
    walker_index: int
    walker_area_name: str
    total_walkers_allowed_for_assigned_area: int


class WorkerFactory:
    def __init__(self, args, mapping_manager: MappingManager, mitm_mapper: MitmMapper, db_wrapper: DbWrapper,
                 pogo_windows: PogoWindows, event):
        self.__args = args
        self.__mapping_manager: MappingManager = mapping_manager
        self.__mitm_mapper: MitmMapper = mitm_mapper
        self.__db_wrapper: DbWrapper = db_wrapper
        self.__pogo_windows: PogoWindows = pogo_windows
        self.__event = event

    async def __get_walker_index(self, devicesettings, origin):
        walker_index = devicesettings.get('walker_area_index', 0)
        if walker_index > 0:
            # check status of last area
            if not devicesettings.get('finished', False):
                logger.info(
                    'Something wrong with last round - get back to old area')
                walker_index -= 1
                self.__mapping_manager.set_devicesetting_value_of(origin, 'walker_area_index',
                                                                  walker_index)
            else:
                logger.debug('Previous area was finished, move on')
        return walker_index

    async def __initalize_devicesettings(self, origin):
        logger.debug("Initializing devicesettings")
        self.__mapping_manager.set_devicesetting_value_of(origin, 'walker_area_index', 0)
        self.__mapping_manager.set_devicesetting_value_of(origin, 'finished', False)
        self.__mapping_manager.set_devicesetting_value_of(origin, 'last_action_time', None)
        self.__mapping_manager.set_devicesetting_value_of(origin, 'last_cleanup_time', None)
        self.__mapping_manager.set_devicesetting_value_of(origin, 'job', False)
        await asyncio.sleep(1)  # give the settings a moment... (dirty "workaround" against race condition)

    async def __get_walker_settings(self, origin: str, client_mapping: dict, devicesettings: dict) \
            -> Optional[WalkerConfiguration]:
        walker_area_array = client_mapping.get("walker", None)
        if walker_area_array is None:
            logger.error("No valid walker could be found for {}", origin)
            return None

        if devicesettings is not None and "walker_area_index" not in devicesettings:
            await self.__initalize_devicesettings(origin)
        walker_index = await self.__get_walker_index(devicesettings, origin)

        walker_settings: dict = walker_area_array[walker_index]

        # preckeck walker setting
        walker_area_name = walker_area_array[walker_index]['walkerarea']
        while not pre_check_value(walker_settings, self.__event.get_current_event_id()) \
                and walker_index < len(walker_area_array):
            logger.info(
                '{} not using area {} - Walkervalue out of range', str(origin),
                str(self.__mapping_manager.routemanager_get_name(walker_area_name)))
            if walker_index >= len(walker_area_array) - 1:
                logger.error(
                    'Could not find any working area at this time - check your mappings for device: {}',
                    str(origin))
                walker_index = 0
                self.__mapping_manager.set_devicesetting_value_of(origin, 'walker_area_index',
                                                                  walker_index)
                return None
            walker_index += 1
            self.__mapping_manager.set_devicesetting_value_of(origin, 'walker_area_index',
                                                              walker_index)
            walker_settings = walker_area_array[walker_index]
            walker_area_name = walker_area_array[walker_index]['walkerarea']

        logger.debug("Checking walker_area_index length")
        if walker_index >= len(walker_area_array):
            # check if array is smaller than expected - f.e. on the fly changes in mappings.json
            self.__mapping_manager.set_devicesetting_value_of(origin, 'walker_area_index', 0)
            self.__mapping_manager.set_devicesetting_value_of(origin, 'finished', False)
            walker_index = 0

        walker_configuration = WalkerConfiguration(walker_area_name=walker_area_name, walker_index=walker_index,
                                                   walker_settings=walker_settings,
                                                   total_walkers_allowed_for_assigned_area=len(walker_area_array))
        return walker_configuration

    async def __prep_settings(self, origin: str) -> Optional[WalkerConfiguration]:
        last_known_state = {}
        client_mapping = self.__mapping_manager.get_devicemappings_of(origin)
        devicesettings = self.__mapping_manager.get_devicesettings_of(origin)
        logger.info("Setting up routemanagers for {}", str(origin))

        walker_configuration: Optional[WalkerConfiguration] = await self.__get_walker_settings(origin, client_mapping,
                                                                                               devicesettings)
        if walker_configuration is None:
            # logging is done in __get_walker_settings...
            return None

        if walker_configuration.walker_area_name not in self.__mapping_manager.get_all_routemanager_names():
            raise WrongAreaInWalker()

        logger.debug('Devicesettings {}: {}', str(origin), devicesettings)
        logger.info('{} using walker area {} [{}/{}]', str(origin), str(
            self.__mapping_manager.routemanager_get_name(walker_configuration.walker_area_name)),
                    str(walker_configuration.walker_index + 1),
                    str(walker_configuration.total_walkers_allowed_for_assigned_area))
        return walker_configuration

    async def __update_settings_of_origin(self, origin: str, walker_configuration: WalkerConfiguration):
        self.__mapping_manager.set_devicesetting_value_of(origin, 'walker_area_index',
                                                          walker_configuration.walker_index + 1)
        self.__mapping_manager.set_devicesetting_value_of(origin, 'finished', False)
        if walker_configuration.walker_index >= walker_configuration.total_walkers_allowed_for_assigned_area - 1:
            self.__mapping_manager.set_devicesetting_value_of(origin, 'walker_area_index', 0)

        if "last_location" not in self.__mapping_manager.get_devicesettings_of(origin):
            # TODO: I hope this does not cause issues...
            self.__mapping_manager.set_devicesetting_value_of(origin, "last_location", Location(0.0, 0.0))

    async def get_worker_using_settings(self, origin: str, enable_configmode: bool,
                                        communicator: AbstractCommunicator) \
            -> Optional[AbstractWorker]:
        if enable_configmode:
            return self.get_configmode_worker(origin, communicator)

        # not a configmore worker, move on adjusting devicesettings etc
        # TODO: get worker
        walker_configuration: Optional[WalkerConfiguration] = await self.__prep_settings(origin)
        if walker_configuration is None:
            logger.error("Failed to find a walker configuration for {}", origin)
            return None
        logger.debug("Setting up worker for {}", str(origin))
        await self.__update_settings_of_origin(origin, walker_configuration)

        dev_id = self.__mapping_manager.get_all_devicemappings()[origin]['device_id']
        area_id = walker_configuration.walker_settings['walkerarea']
        walker_routemanager_mode: WorkerType = self.__mapping_manager.routemanager_get_mode(
            walker_configuration.walker_area_name
        )
        if dev_id is None or area_id is None or walker_routemanager_mode == WorkerType.UNDEFINED:
            logger.error("Failed to instantiate worker for {} due to invalid settings found", origin)
            return None

        # we can finally create an instance of the worker, bloody hell...
        # TODO: last_known_state has never been used and got kinda deprecated due to devicesettings...
        return self.get_worker(origin, walker_routemanager_mode, communicator, dev_id, {}, area_id,
                               walker_configuration.walker_settings, walker_configuration.walker_area_name)

    def get_worker(self, origin: str, worker_type: WorkerType, communicator: AbstractCommunicator,
                   dev_id: str, last_known_state: dict, area_id: int,
                   walker_settings: dict, walker_area_name: str) -> Optional[AbstractWorker]:
        if origin is None or worker_type is None or worker_type == WorkerType.UNDEFINED:
            return None
        elif worker_type in [WorkerType.CONFIGMODE, WorkerType.CONFIGMODE.value]:
            logger.error("WorkerFactory::get_worker called with configmode arg, use get_configmode_worker instead")
            return None
        # TODO: validate all values
        elif worker_type in [WorkerType.IV_MITM, WorkerType.IV_MITM.value,
                             WorkerType.MON_MITM, WorkerType.MON_MITM.value,
                             WorkerType.RAID_MITM, WorkerType.RAID_MITM.value]:
            return WorkerMITM(self.__args, dev_id, origin, last_known_state, communicator, area_id=area_id,
                              routemanager_name=walker_area_name, mitm_mapper=self.__mitm_mapper,
                              mapping_manager=self.__mapping_manager, db_wrapper=self.__db_wrapper,
                              pogo_window_manager=self.__pogo_windows, walker=walker_settings, event=self.__event)
        elif worker_type in [WorkerType.STOPS, WorkerType.STOPS.value]:
            return WorkerQuests(self.__args, dev_id, origin, last_known_state, communicator, area_id=area_id,
                                routemanager_name=walker_area_name, mitm_mapper=self.__mitm_mapper,
                                mapping_manager=self.__mapping_manager, db_wrapper=self.__db_wrapper,
                                pogo_window_manager=self.__pogo_windows, walker=walker_settings, event=self.__event)
        elif worker_type in [WorkerType.IDLE, WorkerType.IDLE.value]:
            return WorkerConfigmode(self.__args, dev_id, origin, communicator, walker=walker_settings,
                                    mapping_manager=self.__mapping_manager, mitm_mapper=self.__mitm_mapper,
                                    db_wrapper=self.__db_wrapper, area_id=area_id, routemanager_name=walker_area_name,
                                    event=self.__event)
        else:
            logger.error("WorkerFactor::get_worker failed to create a worker...")
            return None

    def get_configmode_worker(self, origin: str, communicator: AbstractCommunicator) -> WorkerConfigmode:
        dev_id = self.__mapping_manager.get_all_devicemappings()[origin]['device_id']
        worker = WorkerConfigmode(args=self.__args,
                                  dev_id=dev_id,
                                  origin=origin,
                                  communicator=communicator,
                                  walker=None,
                                  mapping_manager=self.__mapping_manager,
                                  mitm_mapper=self.__mitm_mapper,
                                  db_wrapper=self.__db_wrapper,
                                  area_id=0,
                                  routemanager_name=None,
                                  event=self.__event)
        return worker

