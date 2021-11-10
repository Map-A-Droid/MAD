import asyncio
from typing import Optional, Tuple, NamedTuple

from loguru import logger

from mapadroid.data_handler.mitm_data.AbstractMitmMapper import AbstractMitmMapper
from mapadroid.data_handler.stats.AbstractStatsHandler import AbstractStatsHandler
from mapadroid.db.DbWrapper import DbWrapper
from mapadroid.db.model import SettingsDevicepool, SettingsDevice, SettingsWalkerarea
from mapadroid.geofence.geofenceHelper import GeofenceHelper
from mapadroid.mapping_manager.MappingManager import DeviceMappingsEntry, MappingManager
from mapadroid.mapping_manager.MappingManagerDevicemappingKey import MappingManagerDevicemappingKey
from mapadroid.ocr.pogoWindows import PogoWindows
from mapadroid.ocr.screenPath import WordToScreenMatching
from mapadroid.utils.collections import Location
from mapadroid.utils.madGlobals import WrongAreaInWalker
from mapadroid.utils.routeutil import pre_check_value
from mapadroid.websocket.AbstractCommunicator import AbstractCommunicator
from mapadroid.worker.WorkerState import WorkerState
from mapadroid.worker.WorkerType import WorkerType
from mapadroid.worker.strategy.AbstractWorkerStrategy import AbstractWorkerStrategy
from mapadroid.worker.strategy.NopStrategy import NopStrategy
from mapadroid.worker.strategy.QuestStrategy import QuestStrategy
from mapadroid.worker.strategy.WorkerMitmStrategy import WorkerMitmStrategy


class WalkerConfiguration(NamedTuple):
    walker_settings: SettingsWalkerarea
    walker_index: int
    area_id: int
    total_walkers_allowed_for_assigned_area: int


class StrategyFactory:
    def __init__(self, args, mapping_manager: MappingManager, mitm_mapper: AbstractMitmMapper,
                 stats_handler: AbstractStatsHandler, db_wrapper: DbWrapper, pogo_windows: PogoWindows, event):
        self.__args = args
        self.__mapping_manager: MappingManager = mapping_manager
        self.__mitm_mapper: AbstractMitmMapper = mitm_mapper
        self.__stats_handler: AbstractStatsHandler = stats_handler
        self.__db_wrapper: DbWrapper = db_wrapper
        self.__pogo_windows: PogoWindows = pogo_windows
        self.__event = event

    async def get_strategy_using_settings(self, origin: str, enable_configmode: bool,
                                          communicator: AbstractCommunicator,
                                          worker_state: WorkerState) -> Optional[AbstractWorkerStrategy]:
        if enable_configmode:
            return await self.get_strategy(worker_type=WorkerType.CONFIGMODE,
                                           area_id=0,
                                           communicator=communicator,
                                           walker_settings=None,
                                           worker_state=worker_state)

        # not a configmode worker, move on adjusting devicesettings etc
        walker_configuration: Optional[WalkerConfiguration] = await self.__prep_settings(origin)
        if walker_configuration is None:
            logger.error("Failed to find a walker configuration")
            return await self.get_strategy(worker_type=WorkerType.CONFIGMODE,
                                           area_id=0,
                                           communicator=communicator,
                                           walker_settings=None,
                                           worker_state=worker_state)
        logger.debug("Setting up worker")
        await self.__update_settings_of_origin(origin, walker_configuration)

        devicesettings: Optional[Tuple[SettingsDevice, SettingsDevicepool]] = await self.__mapping_manager \
            .get_devicesettings_of(origin)
        dev_id: int = devicesettings[0].device_id
        walker_routemanager_mode: WorkerType = await self.__mapping_manager.routemanager_get_mode(
            walker_configuration.area_id
        )
        if not dev_id or not walker_configuration.walker_settings or walker_routemanager_mode == WorkerType.UNDEFINED:
            logger.error("Failed to instantiate worker due to invalid settings found")
            return await self.get_strategy(worker_type=WorkerType.CONFIGMODE,
                                           area_id=0,
                                           communicator=communicator,
                                           walker_settings=walker_configuration.walker_settings,
                                           worker_state=worker_state)

        return await self.get_strategy(worker_type=walker_routemanager_mode,
                                       area_id=walker_configuration.area_id,
                                       communicator=communicator,
                                       walker_settings=walker_configuration.walker_settings,
                                       worker_state=worker_state)

    async def get_strategy(self, worker_type: WorkerType,
                           area_id: int,
                           communicator: AbstractCommunicator,
                           walker_settings: Optional[SettingsWalkerarea],
                           worker_state: WorkerState) -> Optional[AbstractWorkerStrategy]:
        strategy: Optional[AbstractWorkerStrategy] = None
        word_to_screen_matching: WordToScreenMatching = await WordToScreenMatching.create(communicator=communicator,
                                                                                          pogo_win_manager=self.__pogo_windows,
                                                                                          origin=worker_state.origin,
                                                                                          resocalc=worker_state.resolution_calculator,
                                                                                          mapping_mananger=self.__mapping_manager)
        if not worker_type or worker_type in [WorkerType.UNDEFINED, WorkerType.CONFIGMODE, WorkerType.IDLE]:
            logger.info("Either no valid worker type or idle was passed, creating idle strategy.")
            strategy = NopStrategy(area_id=area_id,
                                   communicator=communicator, mapping_manager=self.__mapping_manager,
                                   db_wrapper=self.__db_wrapper,
                                   word_to_screen_matching=word_to_screen_matching,
                                   pogo_windows_handler=self.__pogo_windows,
                                   walker=walker_settings,
                                   worker_state=worker_state)
        elif worker_type in [WorkerType.IV_MITM, WorkerType.MON_MITM, WorkerType.RAID_MITM]:
            strategy = WorkerMitmStrategy(area_id=area_id,
                                          communicator=communicator, mapping_manager=self.__mapping_manager,
                                          db_wrapper=self.__db_wrapper,
                                          word_to_screen_matching=word_to_screen_matching,
                                          pogo_windows_handler=self.__pogo_windows,
                                          walker=walker_settings,
                                          worker_state=worker_state,
                                          mitm_mapper=self.__mitm_mapper,
                                          stats_handler=self.__stats_handler)
        elif worker_type in [WorkerType.STOPS]:
            strategy = QuestStrategy(area_id=area_id,
                                     communicator=communicator, mapping_manager=self.__mapping_manager,
                                     db_wrapper=self.__db_wrapper,
                                     word_to_screen_matching=word_to_screen_matching,
                                     pogo_windows_handler=self.__pogo_windows,
                                     walker=walker_settings,
                                     worker_state=worker_state,
                                     mitm_mapper=self.__mitm_mapper,
                                     stats_handler=self.__stats_handler)
        else:
            logger.error("WorkerFactor::get_worker failed to create a worker...")
        return strategy

    async def __prep_settings(self, origin: str) -> Optional[WalkerConfiguration]:
        logger.info("Setting up routemanagers")

        walker_configuration: Optional[WalkerConfiguration] = await self.__get_walker_settings(origin)
        if walker_configuration is None:
            # logging is done in __get_walker_settings...
            return None

        if walker_configuration.area_id not in await self.__mapping_manager.get_all_routemanager_ids():
            raise WrongAreaInWalker()

        logger.info('using walker area {} [{}/{}]',
                    await self.__mapping_manager.routemanager_get_name(walker_configuration.area_id),
                    walker_configuration.walker_index + 1,
                    walker_configuration.total_walkers_allowed_for_assigned_area)
        return walker_configuration

    async def __initalize_devicesettings(self, origin):
        logger.debug("Initializing devicesettings")
        await self.__mapping_manager.set_devicesetting_value_of(origin,
                                                                MappingManagerDevicemappingKey.WALKER_AREA_INDEX, 0)
        await self.__mapping_manager.set_devicesetting_value_of(origin, MappingManagerDevicemappingKey.FINISHED, False)
        await self.__mapping_manager.set_devicesetting_value_of(origin,
                                                                MappingManagerDevicemappingKey.LAST_LOCATION_TIME, None)
        await self.__mapping_manager.set_devicesetting_value_of(origin,
                                                                MappingManagerDevicemappingKey.LAST_CLEANUP_TIME, None)
        await self.__mapping_manager.set_devicesetting_value_of(origin, MappingManagerDevicemappingKey.JOB_ACTIVE,
                                                                False)
        await asyncio.sleep(1)  # give the settings a moment... (dirty "workaround" against race condition)

    async def __get_walker_settings(self, origin: str) \
            -> Optional[WalkerConfiguration]:
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
            logger.warning('No area defined for the current walker')
            return None

        # preckeck walker setting using the geofence_included's first location
        location = await self.__area_middle_of_fence(walker_settings)
        while not pre_check_value(walker_settings, self.__event.get_current_event_id(), location) \
                and client_mapping.walker_area_index < len(client_mapping.walker_areas):
            logger.info('not using area {} - Walkervalue out of range',
                        await self.__mapping_manager.routemanager_get_name(walker_settings.area_id))
            if client_mapping.walker_area_index >= len(client_mapping.walker_areas) - 1:
                logger.warning('Cannot find any active area defined for current time. Check Walker entries')
                client_mapping.walker_area_index = 0
                await self.__mapping_manager.set_devicesetting_value_of(origin,
                                                                        MappingManagerDevicemappingKey.WALKER_AREA_INDEX,
                                                                        client_mapping.walker_area_index)
                return None
            client_mapping.walker_area_index += 1
            await self.__mapping_manager.set_devicesetting_value_of(origin,
                                                                    MappingManagerDevicemappingKey.WALKER_AREA_INDEX,
                                                                    client_mapping.walker_area_index)
            walker_settings = client_mapping.walker_areas[client_mapping.walker_area_index]
            location = await self.__area_middle_of_fence(walker_settings)

        logger.debug("Checking walker_area_index length")
        if client_mapping.walker_area_index >= len(client_mapping.walker_areas):
            # check if array is smaller than expected - f.e. on the fly changes in mappings.json
            await self.__mapping_manager.set_devicesetting_value_of(origin,
                                                                    MappingManagerDevicemappingKey.WALKER_AREA_INDEX, 0)
            await self.__mapping_manager.set_devicesetting_value_of(origin, MappingManagerDevicemappingKey.FINISHED,
                                                                    False)
            client_mapping.walker_area_index = 0

        walker_configuration = WalkerConfiguration(area_id=walker_settings.area_id,
                                                   walker_index=client_mapping.walker_area_index,
                                                   walker_settings=walker_settings,
                                                   total_walkers_allowed_for_assigned_area=len(
                                                       client_mapping.walker_areas))
        return walker_configuration

    async def __area_middle_of_fence(self, walker_settings: SettingsWalkerarea):
        geofence_helper: Optional[GeofenceHelper] = await self.__mapping_manager.routemanager_get_geofence_helper(
            walker_settings.area_id)
        location: Optional[Location] = None
        if geofence_helper:
            lat, lng = geofence_helper.get_middle_from_fence()
            location = Location(lat, lng)
        return location

    async def __update_walker_index(self, origin: str, mapping_entry: DeviceMappingsEntry) -> None:
        if mapping_entry.walker_area_index > 0:
            # check status of last area
            if not mapping_entry.finished:
                logger.info('Something wrong with last round - get back to old area')
                mapping_entry.walker_area_index -= 1
                await self.__mapping_manager \
                    .set_devicesetting_value_of(origin, MappingManagerDevicemappingKey.WALKER_AREA_INDEX,
                                                mapping_entry.walker_area_index)
            else:
                logger.debug('Previous area was finished, move on')

    async def __update_settings_of_origin(self, origin: str, walker_configuration: WalkerConfiguration):
        await self.__mapping_manager.set_devicesetting_value_of(origin,
                                                                MappingManagerDevicemappingKey.WALKER_AREA_INDEX,
                                                                walker_configuration.walker_index + 1)
        await self.__mapping_manager.set_devicesetting_value_of(origin, MappingManagerDevicemappingKey.FINISHED, False)
        if walker_configuration.walker_index >= walker_configuration.total_walkers_allowed_for_assigned_area - 1:
            await self.__mapping_manager.set_devicesetting_value_of(origin,
                                                                    MappingManagerDevicemappingKey.WALKER_AREA_INDEX, 0)

        if not (await self.__mapping_manager.get_devicemappings_of(origin)).last_location:
            # TODO: Validate working
            await self.__mapping_manager.set_devicesetting_value_of(origin,
                                                                    MappingManagerDevicemappingKey.LAST_LOCATION,
                                                                    Location(0.0, 0.0))
