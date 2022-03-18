import asyncio
import os
import sys
from asyncio import CancelledError, Task
from typing import Optional, Union

from aioredis import Redis

from mapadroid.data_handler.grpc.StatsHandlerClient import StatsHandlerClient
from mapadroid.data_handler.grpc.StatsHandlerClientConnector import StatsHandlerClientConnector
from mapadroid.data_handler.mitm_data.AbstractMitmMapper import AbstractMitmMapper
from mapadroid.data_handler.stats.AbstractStatsHandler import AbstractStatsHandler
from mapadroid.data_handler.grpc.MitmMapperClient import MitmMapperClient
from mapadroid.data_handler.grpc.MitmMapperClientConnector import \
    MitmMapperClientConnector
from mapadroid.data_handler.mitm_data.MitmMapperType import MitmMapperType
from mapadroid.data_handler.mitm_data.RedisMitmMapper import RedisMitmMapper
from mapadroid.db.DbFactory import DbFactory
from mapadroid.mad_apk import get_storage_obj
from mapadroid.madmin.madmin import MADmin
from mapadroid.mapping_manager.MappingManager import MappingManager
from mapadroid.mapping_manager.MappingManagerServer import MappingManagerServer
from mapadroid.ocr.pogoWindows import PogoWindows
from mapadroid.plugins.pluginBase import PluginCollection
from mapadroid.utils.EnvironmentUtil import setup_runtime, setup_loggers
from mapadroid.utils.SystemStatsUtil import get_system_infos
from mapadroid.utils.logging import (LoggerEnums, get_logger,
                                     init_logging)
from mapadroid.utils.madGlobals import application_args, terminate_mad
from mapadroid.utils.pogoevent import PogoEvent
from mapadroid.utils.questGen import QuestGen
from mapadroid.utils.rarity import Rarity
from mapadroid.utils.updater import DeviceUpdater
from mapadroid.webhook.webhookworker import WebhookWorker
from mapadroid.websocket.WebsocketServer import WebsocketServer

try:
    import uvloop

    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
    uvloop.install()
except Exception as e:
    # uvloop is optional
    pass

py_version = sys.version_info
if py_version.major < 3 or (py_version.major == 3 and py_version.minor < 9):
    print("MAD requires at least python 3.9! Your version: {}.{}"
          .format(py_version.major, py_version.minor))
    sys.exit(1)


async def start():
    jobstatus: dict = {}
    stats_handler: Optional[AbstractStatsHandler] = None
    mitm_mapper: Optional[AbstractMitmMapper] = None
    pogo_win_manager: Optional[PogoWindows] = None
    webhook_task: Optional[Task] = None  # Thread for WebHooks
    webhook_worker: Optional[WebhookWorker] = None
    t_usage: Optional[Task] = None

    setup_runtime()
    if application_args.config_mode:
        logger.info('Starting MAD in config mode')
    else:
        logger.info('Starting MAD')

    if application_args.config_mode and application_args.only_routes:
        logger.error('Unable to run with config_mode and only_routes.  Only use one option')
        sys.exit(1)
    if not application_args.only_scan and not application_args.only_routes:
        logger.error("No runmode selected. \nAllowed modes:\n"
                     " -os    ---- start scanner/devicecontroller\n"
                     " -or    ---- only calculate routes")
        sys.exit(1)
    # Elements that should initialized regardless of the functionality being used
    db_wrapper, db_exec = await DbFactory.get_wrapper(application_args)

    # TODO: MADPatcher(args, data_manager)
    #  data_manager.clear_on_boot()
    #  data_manager.fix_routecalc_on_boot()
    event = PogoEvent(application_args, db_wrapper)
    event_task: Optional[Task] = await event.start_event_checker()
    # Do not remove this sleep unless you have solved the race condition on boot with the logger
    await asyncio.sleep(.1)
    # TODO: Externalize MappingManager as a service
    mapping_manager: MappingManager = MappingManager(db_wrapper,
                                                     application_args,
                                                     configmode=application_args.config_mode)
    await mapping_manager.setup()
    mapping_manager_grpc_server = MappingManagerServer(mapping_manager)
    await mapping_manager_grpc_server.start()

    if application_args.only_routes:
        logger.info('Running in route recalculation mode. MAD will exit once complete')
        recalc_in_progress = True
        while recalc_in_progress:
            await asyncio.sleep(5)
            sql = "SELECT COUNT(*) > 0 FROM `settings_routecalc` WHERE `recalc_status` = 1"
            # TODO recalc_in_progress = db_wrapper.autofetch_value(sql)
        logger.info("Done calculating routes!")
        # TODO: shutdown managers properly...
        sys.exit(0)
    storage_elem = await get_storage_obj(application_args, db_wrapper)
    if not application_args.config_mode:
        pogo_win_manager = PogoWindows(application_args.temp_path, application_args.ocr_thread_count)
        if application_args.mitmmapper_type == MitmMapperType.grpc:
            # TODO: Stats handler client
            mitm_mapper_connector = MitmMapperClientConnector()
            await mitm_mapper_connector.start()
            mitm_mapper: MitmMapperClient = await mitm_mapper_connector.get_client()
        elif application_args.mitmmapper_type == MitmMapperType.redis:
            mitm_mapper: RedisMitmMapper = RedisMitmMapper(db_wrapper)
            await mitm_mapper.start()
        else:
            logger.critical("Unsupported MitmMapper type for multi-host/process setup {}", application_args.mitmmapper_type)
            sys.exit(1)

    stats_handler_connector = StatsHandlerClientConnector()
    await stats_handler_connector.start()
    stats_handler: StatsHandlerClient = await stats_handler_connector.get_client()
    await stats_handler.start()

    quest_gen: QuestGen = QuestGen()
    await quest_gen.setup()
    logger.info('Starting websocket server on port {}'.format(str(application_args.ws_port)))
    ws_server = WebsocketServer(args=application_args,
                                mitm_mapper=mitm_mapper,
                                stats_handler=stats_handler,
                                db_wrapper=db_wrapper,
                                mapping_manager=mapping_manager,
                                pogo_window_manager=pogo_win_manager,
                                event=event,
                                enable_configmode=application_args.config_mode)
    # TODO: module/service?
    await ws_server.start_server()

    device_updater = DeviceUpdater(ws_server, application_args, jobstatus, db_wrapper, storage_elem)
    await device_updater.init_jobs()
    if not application_args.config_mode:
        if application_args.webhook:
            rarity = Rarity(application_args, db_wrapper)
            await rarity.start_dynamic_rarity()
            webhook_worker = WebhookWorker(application_args, db_wrapper, mapping_manager, rarity, quest_gen)
            webhook_task = await webhook_worker.start()
            # TODO: Stop webhook_task properly

    madmin = MADmin(application_args, db_wrapper, ws_server, mapping_manager, device_updater, jobstatus, storage_elem,
                    quest_gen)

    # starting plugin system
    plugin_parts = {
        'args': application_args,
        'db_wrapper': db_wrapper,
        'device_updater': device_updater,
        'event': event,
        'jobstatus': jobstatus,
        'logger': get_logger(LoggerEnums.plugin),
        'madmin': madmin,
        'mapping_manager': mapping_manager,
        'mitm_mapper': mitm_mapper,
        'storage_elem': storage_elem,
        'webhook_worker': webhook_worker,
        'ws_server': ws_server,
    }

    mad_plugins = PluginCollection('plugins', plugin_parts)
    await mad_plugins.finish_init()
    # MADmin needs to be started after sub-applications (plugins) have been added

    if not application_args.disable_madmin or application_args.config_mode:
        logger.info("Starting Madmin on port {}", str(application_args.madmin_port))
        madmin_app_runner = await madmin.madmin_start()

    if application_args.statistic:
        logger.info("Starting statistics collector")
        loop = asyncio.get_running_loop()
        t_usage = loop.create_task(get_system_infos(db_wrapper))
    logger.info("MAD is now running.....")
    exit_code = 0
    try:
        while True:
            await asyncio.sleep(10)
    except (KeyboardInterrupt, CancelledError):
        logger.info("Shutdown signal received")
    finally:
        try:
            logger.success("Stop called")
            terminate_mad.set()
            # now cleanup all threads...
            # TODO: check against args or init variables to None...
            if t_usage:
                t_usage.cancel()
            if device_updater is not None:
                device_updater.stop_updater()
            if webhook_task is not None:
                logger.info("Waiting for webhook-thread to exit")
                webhook_task.cancel()
            if ws_server is not None:
                logger.info("Stopping websocket server")
                await ws_server.stop_server()
                logger.info("Waiting for websocket-thread to exit")
                # t_ws.cancel()
            if mapping_manager:
                mapping_manager.shutdown()
            # if storage_manager is not None:
            #    logger.debug('Stopping storage manager')
            #    storage_manager.shutdown()
            if event_task:
                event_task.cancel()
            if db_exec is not None:
                logger.debug("Calling db_pool_manager shutdown")
                cache: Redis = await db_wrapper.get_cache()
                await cache.close()
                db_exec.shutdown()
                logger.debug("Done shutting down db_pool_manager")
        except Exception:
            logger.opt(exception=True).critical("An unhandled exception occurred during shutdown!")
        logger.info("Done shutting down")
        logger.debug(str(sys.exc_info()))
        sys.exit(exit_code)


if __name__ == "__main__":
    global application_args
    os.environ['LANGUAGE'] = application_args.language
    init_logging(application_args)
    setup_loggers()
    logger = get_logger(LoggerEnums.system)

    loop = asyncio.get_event_loop()
    # signal.signal(signal.SIGINT, signal_handler)
    # signal.signal(signal.SIGTERM, signal_handler)

    loop_being_run = loop
    try:
        # loop.run_until_complete(start())
        asyncio.run(start(), debug=True)
    except (KeyboardInterrupt, Exception) as e:
        # shutdown(loop_being_run)
        logger.info(f"Shutting down. {e}")
        logger.exception(e)
