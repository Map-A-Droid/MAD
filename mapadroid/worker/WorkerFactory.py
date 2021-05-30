import asyncio
from typing import NamedTuple, Optional, Tuple

from mapadroid.db.DbWrapper import DbWrapper
from mapadroid.db.model import SettingsDevice, SettingsDevicepool, SettingsWalkerarea
from mapadroid.mitm_receiver.MitmMapper import MitmMapper
from mapadroid.ocr.pogoWindows import PogoWindows
from mapadroid.mapping_manager.MappingManagerDevicemappingKey import MappingManagerDevicemappingKey
from mapadroid.utils.collections import Location
from mapadroid.utils.logging import LoggerEnums, get_logger, get_origin_logger
from mapadroid.utils.madGlobals import WrongAreaInWalker
from mapadroid.mapping_manager.MappingManager import MappingManager, DeviceMappingsEntry
from mapadroid.utils.routeutil import pre_check_value
from mapadroid.websocket.AbstractCommunicator import AbstractCommunicator
from mapadroid.worker.AbstractWorker import AbstractWorker
from mapadroid.worker.WorkerConfigmode import WorkerConfigmode
from mapadroid.worker.WorkerMITM import WorkerMITM
from mapadroid.worker.WorkerQuests import WorkerQuests
from mapadroid.worker.WorkerType import WorkerType

logger = get_logger(LoggerEnums.worker)


class WalkerConfiguration(NamedTuple):
    walker_settings: SettingsWalkerarea
    walker_index: int
    area_id: int
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

    async def __update_walker_index(self, origin: str, mapping_entry: DeviceMappingsEntry) -> None:
        origin_logger = get_origin_logger(logger, origin=origin)
        if mapping_entry.walker_area_index > 0:
            # check status of last area
            if not mapping_entry.finished:
                origin_logger.info('Something wrong with last round - get back to old area')
                mapping_entry.walker_area_index -= 1
                await self.__mapping_manager\
                    .set_devicesetting_value_of(origin, MappingManagerDevicemappingKey.WALKER_AREA_INDEX,
                                                mapping_entry.walker_area_index)
            else:
                origin_logger.debug('Previous area was finished, move on')

    async def __initalize_devicesettings(self, origin):
        logger.debug("Initializing devicesettings")
        await self.__mapping_manager.set_devicesetting_value_of(origin, MappingManagerDevicemappingKey.WALKER_AREA_INDEX, 0)
        await self.__mapping_manager.set_devicesetting_value_of(origin, MappingManagerDevicemappingKey.FINISHED, False)
        await self.__mapping_manager.set_devicesetting_value_of(origin, MappingManagerDevicemappingKey.LAST_LOCATION_TIME, None)
        await self.__mapping_manager.set_devicesetting_value_of(origin, MappingManagerDevicemappingKey.LAST_CLEANUP_TIME, None)
        await self.__mapping_manager.set_devicesetting_value_of(origin, MappingManagerDevicemappingKey.JOB_ACTIVE, False)
        await asyncio.sleep(1)  # give the settings a moment... (dirty "workaround" against race condition)

    async def __get_walker_settings(self, origin: str) \
            -> Optional[WalkerConfiguration]:
        origin_logger = get_origin_logger(logger, origin=origin)
        client_mapping: Optional[DeviceMappingsEntry] = await self.__mapping_manager.get_devicemappings_of(origin)
        if not client_mapping.walker_areas:
            logger.warning("No valid walker could be found for {}", origin)
            return None

        if client_mapping.walker_area_index < 0:
            await self.__initalize_devicesettings(origin)
        await self.__update_walker_index(origin, mapping_entry=client_mapping)

        try:
            walker_settings: SettingsWalkerarea = client_mapping.walker_areas[client_mapping.walker_area_index]
        except IndexError:
            origin_logger.warning('No area defined for the current walker')
            return None

        # preckeck walker setting
        while not pre_check_value(walker_settings, self.__event.get_current_event_id()) \
                and client_mapping.walker_area_index < len(client_mapping.walker_areas):
            origin_logger.info('not using area {} - Walkervalue out of range',
                               await self.__mapping_manager.routemanager_get_name(walker_settings.area_id))
            if client_mapping.walker_area_index >= len(client_mapping.walker_areas) - 1:
                origin_logger.warning('Cannot find any active area defined for current time. Check Walker entries')
                client_mapping.walker_area_index = 0
                await self.__mapping_manager.set_devicesetting_value_of(origin, MappingManagerDevicemappingKey.WALKER_AREA_INDEX,
                                                                  client_mapping.walker_area_index)
                return None
            client_mapping.walker_area_index += 1
            await self.__mapping_manager.set_devicesetting_value_of(origin, MappingManagerDevicemappingKey.WALKER_AREA_INDEX,
                                                              client_mapping.walker_area_index)
            walker_settings = client_mapping.walker_areas[client_mapping.walker_area_index]

        origin_logger.debug("Checking walker_area_index length")
        if client_mapping.walker_area_index >= len(client_mapping.walker_areas):
            # check if array is smaller than expected - f.e. on the fly changes in mappings.json
            await self.__mapping_manager.set_devicesetting_value_of(origin, MappingManagerDevicemappingKey.WALKER_AREA_INDEX, 0)
            await self.__mapping_manager.set_devicesetting_value_of(origin, MappingManagerDevicemappingKey.FINISHED, False)
            client_mapping.walker_area_index = 0

        walker_configuration = WalkerConfiguration(area_id=walker_settings.area_id, walker_index=client_mapping.walker_area_index,
                                                   walker_settings=walker_settings,
                                                   total_walkers_allowed_for_assigned_area=len(client_mapping.walker_areas))
        return walker_configuration

    async def __prep_settings(self, origin: str) -> Optional[WalkerConfiguration]:
        origin_logger = get_origin_logger(logger, origin=origin)
        origin_logger.info("Setting up routemanagers")

        walker_configuration: Optional[WalkerConfiguration] = await self.__get_walker_settings(origin)
        if walker_configuration is None:
            # logging is done in __get_walker_settings...
            return None

        if walker_configuration.area_id not in await self.__mapping_manager.get_all_routemanager_ids():
            raise WrongAreaInWalker()

        origin_logger.info('using walker area {} [{}/{}]',
                           await self.__mapping_manager.routemanager_get_name(walker_configuration.area_id),
                           walker_configuration.walker_index + 1,
                           walker_configuration.total_walkers_allowed_for_assigned_area)
        return walker_configuration

    async def __update_settings_of_origin(self, origin: str, walker_configuration: WalkerConfiguration):
        await self.__mapping_manager.set_devicesetting_value_of(origin, MappingManagerDevicemappingKey.WALKER_AREA_INDEX,
                                                          walker_configuration.walker_index + 1)
        await self.__mapping_manager.set_devicesetting_value_of(origin, MappingManagerDevicemappingKey.FINISHED, False)
        if walker_configuration.walker_index >= walker_configuration.total_walkers_allowed_for_assigned_area - 1:
            await self.__mapping_manager.set_devicesetting_value_of(origin, MappingManagerDevicemappingKey.WALKER_AREA_INDEX, 0)

        if not (await self.__mapping_manager.get_devicemappings_of(origin)).last_location:
            # TODO: Validate working
            await self.__mapping_manager.set_devicesetting_value_of(origin, MappingManagerDevicemappingKey.LAST_LOCATION, Location(0.0, 0.0))

    async def get_worker_using_settings(self, origin: str, enable_configmode: bool,
                                        communicator: AbstractCommunicator) \
            -> Optional[AbstractWorker]:
        origin_logger = get_origin_logger(logger, origin=origin)
        if enable_configmode:
            return await self.get_configmode_worker(origin, communicator)

        # not a configmore worker, move on adjusting devicesettings etc
        # TODO: get worker
        walker_configuration: Optional[WalkerConfiguration] = await self.__prep_settings(origin)
        if walker_configuration is None:
            origin_logger.warning("Failed to find a walker configuration")
            return None
        origin_logger.debug("Setting up worker")
        await self.__update_settings_of_origin(origin, walker_configuration)

        devicesettings: Optional[Tuple[SettingsDevice, SettingsDevicepool]] = await self.__mapping_manager\
            .get_devicesettings_of(origin)
        dev_id: int = devicesettings[0].device_id
        walker_routemanager_mode: WorkerType = await self.__mapping_manager.routemanager_get_mode(
            walker_configuration.area_id
        )
        if not dev_id or not walker_configuration.walker_settings or walker_routemanager_mode == WorkerType.UNDEFINED:
            origin_logger.error("Failed to instantiate worker due to invalid settings found")
            return None

        # we can finally create an instance of the worker, bloody hell...
        # TODO: last_known_state has never been used and got kinda deprecated due to devicesettings...
        return self.get_worker(origin, walker_routemanager_mode, communicator, dev_id, {},
                               walker_configuration.walker_settings.area_id,
                               walker_configuration.walker_settings, walker_configuration.area_id)

    def get_worker(self, origin: str, worker_type: WorkerType, communicator: AbstractCommunicator,
                   dev_id: int, last_known_state: dict, area_id: int,
                   walker_settings: SettingsWalkerarea, walker_area_id: int) -> Optional[AbstractWorker]:
        origin_logger = get_origin_logger(logger, origin=origin)
        if origin is None or worker_type is None or worker_type == WorkerType.UNDEFINED:
            return None
        elif worker_type in [WorkerType.CONFIGMODE, WorkerType.CONFIGMODE.value]:
            origin_logger.error("WorkerFactory::get_worker called with configmode arg, use get_configmode_worker"
                                "instead")
            return None
        # TODO: validate all values
        elif worker_type in [WorkerType.IV_MITM, WorkerType.IV_MITM.value,
                             WorkerType.MON_MITM, WorkerType.MON_MITM.value,
                             WorkerType.RAID_MITM, WorkerType.RAID_MITM.value]:
            return WorkerMITM(self.__args, dev_id, origin, last_known_state, communicator, area_id=area_id,
                              routemanager_id=walker_area_id, mitm_mapper=self.__mitm_mapper,
                              mapping_manager=self.__mapping_manager, db_wrapper=self.__db_wrapper,
                              pogo_window_manager=self.__pogo_windows, walker=walker_settings, event=self.__event)
        elif worker_type in [WorkerType.STOPS, WorkerType.STOPS.value]:
            return WorkerQuests(self.__args, dev_id, origin, last_known_state, communicator, area_id=area_id,
                                routemanager_id=walker_area_id, mitm_mapper=self.__mitm_mapper,
                                mapping_manager=self.__mapping_manager, db_wrapper=self.__db_wrapper,
                                pogo_window_manager=self.__pogo_windows, walker=walker_settings, event=self.__event)
        elif worker_type in [WorkerType.IDLE, WorkerType.IDLE.value]:
            return WorkerConfigmode(self.__args, dev_id, origin, communicator, walker=walker_settings,
                                    mapping_manager=self.__mapping_manager, mitm_mapper=self.__mitm_mapper,
                                    db_wrapper=self.__db_wrapper, area_id=area_id, routemanager_id=walker_area_id,
                                    event=self.__event)
        else:
            origin_logger.error("WorkerFactor::get_worker failed to create a worker...")
            return None

    async def get_configmode_worker(self, origin: str, communicator: AbstractCommunicator) -> WorkerConfigmode:
        client_mapping: Optional[DeviceMappingsEntry] = await self.__mapping_manager.get_devicemappings_of(origin)
        worker = WorkerConfigmode(args=self.__args,
                                  dev_id=client_mapping.device_settings.device_id,
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
