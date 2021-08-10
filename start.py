import asyncio
import calendar
import concurrent
import datetime
import gc
import linecache
import logging
import os
import sys
from asyncio import Task, CancelledError
from typing import Optional, Tuple, Any
import functools
import pkg_resources
import psutil
from threading import active_count

from mapadroid.db.DbFactory import DbFactory

from mapadroid.db.helper.TrsUsageHelper import TrsUsageHelper
from mapadroid.mad_apk import get_storage_obj
from mapadroid.mad_apk.abstract_apk_storage import AbstractAPKStorage
from mapadroid.madmin.madmin import MADmin
from mapadroid.mitm_receiver.MitmDataProcessorManager import \
    MitmDataProcessorManager
from mapadroid.data_handler.MitmMapper import MitmMapper
from mapadroid.mitm_receiver.MITMReceiver import MITMReceiver
from mapadroid.ocr.pogoWindows import PogoWindows
from mapadroid.utils.pogoevent import PogoEvent
from mapadroid.utils.logging import LoggerEnums, get_logger, init_logging, InterceptHandler
from mapadroid.utils.madGlobals import terminate_mad, application_args
from mapadroid.mapping_manager.MappingManager import MappingManager
# from mapadroid.utils.pluginBase import PluginCollection
from mapadroid.plugins.pluginBase import PluginCollection
from mapadroid.utils.questGen import install_language
from mapadroid.utils.rarity import Rarity
from mapadroid.utils.updater import DeviceUpdater
from mapadroid.utils.walkerArgs import parse_args
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
if py_version.major < 3 or (py_version.major == 3 and py_version.minor < 7):
    print("MAD requires at least python 3.7! Your version: {}.{}"
          .format(py_version.major, py_version.minor))
    sys.exit(1)


# Patch to make exceptions in threads cause an exception.
def install_task_create_excepthook():
    """
    Workaround for sys.excepthook thread bug
    (https://sourceforge.net/tracker/?func=detail&atid=105470&aid=1230540&group_id=5470).
    Call once from __main__ before creating any threads.
    If using psyco, call psycho.cannotcompile(threading.Thread.run)
    since this replaces a new-style class method.
    """
    loop = asyncio.get_running_loop()
    create_task_old = loop.create_task

    def _handle_task_result(
            task: asyncio.Task,
            *,
            logger: logging.Logger,
            message: str,
            message_args: Tuple[Any, ...] = (),
    ) -> None:
        try:
            task.result()
        except asyncio.CancelledError:
            pass  # Task cancellation should not be logged as an error.
        # Ad the pylint ignore: we want to handle all exceptions here so that the result of the task
        # is properly logged. There is no point re-raising the exception in this callback.
        except Exception as e:  # pylint: disable=broad-except
            logger.exception(e)
            logger.exception(message, *message_args)

    def create_task(*args, **kwargs) -> Task:
        try:
            task: Task = create_task_old(*args, **kwargs)
            task.add_done_callback(
                functools.partial(_handle_task_result, logger=logger)
            )
            return task
        except (KeyboardInterrupt, SystemExit):
            raise
        except BrokenPipeError:
            pass
        except Exception as inner_ex:
            logger.exception(inner_ex)
            #logger.opt(exception=True).critical("An unhandled exception occurred!")

    loop.create_task = create_task


def find_referring_graphs(obj):
    ignore_elems = [locals(), globals(), gc.garbage]

    referrers = (r for r in gc.get_referrers(obj) if r not in ignore_elems)
    for ref in referrers:
        print(type(ref))
        if isinstance(ref, Graph):  # noqa: F821
            # A graph node
            yield ref
        elif isinstance(ref, dict):
            # An instance or other namespace dictionary
            for parent in find_referring_graphs(ref):
                yield parent


async def get_system_infos(db_wrapper):
    pid = os.getpid()
    process_running = psutil.Process(pid)
    gc.set_threshold(5, 1, 1)
    gc.enable()
    await asyncio.sleep(60)
    if application_args.trace:
        import tracemalloc
        tracemalloc.start(5)
    while not terminate_mad.is_set():
        logger.debug('Starting internal Cleanup')
        loop = asyncio.get_running_loop()
        collected, cpu_usage, mem_usage, unixnow = await loop.run_in_executor(
            None, __run_system_stats, process_running)
        async with db_wrapper as session, session:
            await TrsUsageHelper.add(session, application_args.status_name, cpu_usage, mem_usage, collected, unixnow)
            await session.commit()
        await asyncio.sleep(application_args.statistic_interval)

last_snapshot = None
initial_snapshot = None


def display_top(snapshot, key_type='traceback', limit=30):
    import tracemalloc
    snapshot = snapshot.filter_traces((
        tracemalloc.Filter(False, "<frozen importlib._bootstrap>"),
        tracemalloc.Filter(False, "<unknown>"),
    ))
    top_stats = snapshot.statistics(key_type)

    logger.info("Top %s lines" % limit)
    for index, stat in enumerate(top_stats[:limit], 1):
        frame = stat.traceback[0]
        logger.info("#%s: %s:%s: %.1f KiB"
              % (index, frame.filename, frame.lineno, stat.size / 1024))
        line = linecache.getline(frame.filename, frame.lineno).strip()
        if line:
            logger.info('    %s' % line)
            logger.info(stat.traceback.format(10))

    other = top_stats[limit:]
    if other:
        size = sum(stat.size for stat in other)
        logger.info("%s other: %.1f KiB" % (len(other), size / 1024))
    total = sum(stat.size for stat in top_stats)
    logger.info("Total allocated size: %.1f KiB" % (total / 1024))


def __run_system_stats(py):
    global last_snapshot, initial_snapshot
    logger.debug('Collecting...')
    unreachable_objs = gc.collect()
    logger.debug('Unreachable objects: {} - Remaining garbage: {} - Running threads: {}',
                 str(unreachable_objs), str(gc.garbage), str(active_count()))
    for obj in gc.garbage:
        for ref in find_referring_graphs(obj):
            ref.set_next(None)
            del ref  # remove local reference so the node can be deleted
        del obj  # remove local reference so the node can be deleted

    # Clear references held by gc.garbage
    logger.debug('Clearing gc garbage')
    del gc.garbage[:]
    mem_usage = py.memory_info()[0] / 2. ** 30
    cpu_usage = py.cpu_percent()
    logger.info('Instance name: "{}" - Memory usage: {:.3f} GB - CPU usage: {}',
                str(application_args.status_name), mem_usage, str(cpu_usage))
    collected = None
    if application_args.stat_gc:
        collected = gc.collect()
        logger.debug("Garbage collector: collected %d objects." % collected)
    zero = datetime.datetime.utcnow()
    unixnow = calendar.timegm(zero.utctimetuple())

    if application_args.trace:
        import tracemalloc
        new_snapshot = tracemalloc.take_snapshot()
        if last_snapshot:

            try:
                display_top(new_snapshot)
            except Exception as e:
                logger.exception(e)
            top_stats = new_snapshot.compare_to(last_snapshot, 'traceback')
            logger.info("Top of diff")
            for stat in top_stats[:15]:
                logger.info(stat)
                logger.info(stat.traceback.format(15))
            logger.info("Bottom of diff")
            for stat in top_stats[-15:]:
                logger.info(stat)
            if not initial_snapshot:
                initial_snapshot = new_snapshot

            top_stats_to_initial = new_snapshot.compare_to(initial_snapshot, 'traceback')
            logger.info("Top of diff to initial")
            for stat in top_stats_to_initial[:15]:
                logger.info(stat)
                logger.info(stat.traceback.format(15))
            logger.info("Bottom of diff to initial")
            for stat in top_stats_to_initial[-15:]:
                logger.info(stat)
        last_snapshot = new_snapshot

    try:
        import objgraph
        logger.info("show_most_common_types")
        objgraph.show_most_common_types(limit=50, shortnames=False)
        logger.info("show_growth")
        objgraph.show_growth(limit=50, shortnames=False)
        logger.info("get_new_ids")
        objgraph.get_new_ids(limit=50)
        logger.info("Constructing backrefs graph")
        # by_type = objgraph.by_type('builtins.list')
        by_type = objgraph.by_type('StackSummary')
        # by_type = objgraph.by_type('uvloop.Loop')
        # by_type = objgraph.by_type("mapadroid.utils.collections.Location")
        # by_type = objgraph.by_type("TrsSpawn")
        if len(by_type) > 1:
            by_type_empty = [type_filtered for type_filtered in by_type if not type_filtered]
            # by_type_filled = [type_filtered for type_filtered in by_type if type_filtered and "mapadroid" in type_filtered.filename]
            by_type_filled = [type_filtered for type_filtered in by_type if type_filtered]
            logger.warning("Filled: {}, empty: {}, total: {}", len(by_type_filled), len(by_type_empty),
                           len(by_type))
            obj = by_type[-500:]
            # TODO: Filter for lists of dicts...
            # filtered = [type_filtered for type_filtered in by_type if len(type_filtered) > 50]
            del by_type_empty
            del by_type_filled
            del by_type
            # objgraph.show_backrefs(obj, max_depth=10)
            #objgraph.show_backrefs(obj, max_depth=5)
        else:
            logger.warning("Not enough of type to show: {}", len(by_type))
    except Exception as e:
        pass
    logger.info("Done with GC")
    return collected, cpu_usage, mem_usage, unixnow


def create_folder(folder):
    if not os.path.exists(folder):
        logger.info(str(folder) + ' created')
        os.makedirs(folder)


def check_dependencies():
    with open("requirements.txt", "r") as f:
        deps = f.readlines()
        try:
            pkg_resources.require(deps)
        except pkg_resources.VersionConflict as version_error:
            logger.error("Some dependencies aren't met. Required: {} (Installed: {})", version_error.req,
                         version_error.dist)
            logger.error(
                "Most of the times you can fix it by running: pip3 install -r requirements.txt --upgrade")
            sys.exit(1)


async def start():
    device_updater: DeviceUpdater = None
    event: PogoEvent = None
    jobstatus: dict = {}
    # mapping_manager_manager: MappingManagerManager = None
    mapping_manager: Optional[MappingManager] = None
    mitm_receiver_process: MITMReceiver = None
    mitm_mapper: Optional[MitmMapper] = None
    pogo_win_manager: Optional[PogoWindows] = None
    storage_elem: Optional[AbstractAPKStorage] = None
    # storage_manager: Optional[StorageSyncManager] = None
    t_whw: Task = None  # Thread for WebHooks
    t_ws: Task = None  # Thread - WebSocket Server
    webhook_worker: Optional[WebhookWorker] = None
    ws_server: WebsocketServer = None

    logging.getLogger('asyncio').setLevel(logging.DEBUG)
    logging.getLogger('asyncio').addHandler(InterceptHandler(log_section=LoggerEnums.asyncio))
    logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)
    logging.getLogger('sqlalchemy.engine').addHandler(InterceptHandler(log_section=LoggerEnums.database))
    logging.getLogger('aiohttp.access').setLevel(logging.INFO)
    logging.getLogger('aiohttp.access').addHandler(InterceptHandler(log_section=LoggerEnums.aiohttp_access))
    logging.getLogger('aiohttp.client').setLevel(logging.INFO)
    logging.getLogger('aiohttp.client').addHandler(InterceptHandler(log_section=LoggerEnums.aiohttp_access))
    logging.getLogger('aiohttp.internal').setLevel(logging.INFO)
    logging.getLogger('aiohttp.internal').addHandler(InterceptHandler(log_section=LoggerEnums.aiohttp_access))
    logging.getLogger('aiohttp.server').setLevel(logging.INFO)
    logging.getLogger('aiohttp.server').addHandler(InterceptHandler(log_section=LoggerEnums.aiohttp_access))
    logging.getLogger('aiohttp.web').setLevel(logging.INFO)
    logging.getLogger('aiohttp.web').addHandler(InterceptHandler(log_section=LoggerEnums.aiohttp_access))

    if application_args.config_mode:
        logger.info('Starting MAD in config mode')
    else:
        logger.info('Starting MAD')
    # check_dependencies()
    # TODO: globally destroy all threads upon sys.exit() for example
    install_task_create_excepthook()
    create_folder(application_args.file_path)
    create_folder(application_args.upload_path)
    create_folder(application_args.temp_path)
    if application_args.config_mode and application_args.only_routes:
        logger.error('Unable to run with config_mode and only_routes.  Only use one option')
        sys.exit(1)
    if not application_args.only_scan and not application_args.only_routes:
        logger.error("No runmode selected. \nAllowed modes:\n"
                     " -os    ---- start scanner/devicecontroller\n"
                     " -or    ---- only calculate routes")
        sys.exit(1)
    # Elements that should initialized regardless of the functionality being used
    db_wrapper, db_exec = DbFactory.get_wrapper(application_args)
    await db_exec.setup()
    await db_wrapper.setup()

    # TODO: MADPatcher(args, data_manager)
    #  data_manager.clear_on_boot()
    #  data_manager.fix_routecalc_on_boot()
    event = PogoEvent(application_args, db_wrapper)
    await event.start_event_checker()
    # Do not remove this sleep unless you have solved the race condition on boot with the logger
    await asyncio.sleep(.1)
    # TODO: Externalize MappingManager as a service
    mapping_manager: MappingManager = MappingManager(db_wrapper,
                                                     application_args,
                                                     configmode=application_args.config_mode)
    await mapping_manager.setup()
    # TODO: Call init of mapping_manager properly rather than in constructor...

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
        mitm_mapper = MitmMapper(application_args, mapping_manager, db_wrapper)
        await mitm_mapper.start()
    logger.info('Starting PogoDroid Receiver server on port {}'.format(str(application_args.mitmreceiver_port)))

    # TODO: Enable and properly integrate...
    mitm_data_processor_manager = MitmDataProcessorManager(application_args, mitm_mapper, db_wrapper)
    await mitm_data_processor_manager.launch_processors()

    mitm_receiver = MITMReceiver(mitm_mapper, application_args, mapping_manager, db_wrapper,
                                 storage_elem,
                                 mitm_data_processor_manager.get_queue(),
                                 enable_configmode=application_args.config_mode)
    # TODO: Cancel() task lateron
    mitm_receiver_task = await mitm_receiver.start()
    logger.info('Starting websocket server on port {}'.format(str(application_args.ws_port)))
    ws_server = WebsocketServer(args=application_args,
                                mitm_mapper=mitm_mapper,
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
            webhook_worker = WebhookWorker(application_args, db_wrapper, mapping_manager, rarity)
            webhook_task = await webhook_worker.start()
            # TODO: Stop webhook_task properly

    madmin = MADmin(application_args, db_wrapper, ws_server, mapping_manager, device_updater, jobstatus, storage_elem)

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
        'mitm_receiver_process': mitm_receiver_process,
        'storage_elem': storage_elem,
        'webhook_worker': webhook_worker,
        'ws_server': ws_server,
        'mitm_data_processor_manager': mitm_data_processor_manager
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
    device_creator = None
    try:
        if application_args.unit_tests:
            pass
            # from mapadroid.tests.local_api import LocalAPI
            # api_ready = False
            # api = LocalAPI()
            # logger.info('Checking API status')
            # if not data_manager.get_root_resource('device').keys():
            #     from mapadroid.tests.test_utils import ResourceCreator
            #     logger.info('Creating a device')
            #     device_creator = ResourceCreator(api, prefix='MADCore')
            #     res = device_creator.create_valid_resource('device')[0]
            #     mapping_manager.update()
            # max_attempts = 30
            # attempt = 0
            # while not api_ready and attempt < max_attempts:
            #     try:
            #         api.get('/api')
            #         api_ready = True
            #         logger.info('API is ready for unit testing')
            #     except Exception:
            #         attempt += 1
            #         time.sleep(1)
            # if api_ready:
            #     loader = unittest.TestLoader()
            #     start_dir = 'mapadroid/tests/'
            #     suite = loader.discover(start_dir)
            #     runner = unittest.TextTestRunner()
            #     result = runner.run(suite)
            #     exit_code = 0 if result.wasSuccessful() else 1
            #     raise KeyboardInterrupt
            # else:
            #     exit_code = 1
        else:
            while True:
                await asyncio.sleep(10)
    except (KeyboardInterrupt, CancelledError):
        logger.info("Shutdown signal received")
    finally:
        try:
            db_wrapper = None
            logger.success("Stop called")
            if device_creator:
                device_creator.remove_resources()
            terminate_mad.set()
            # now cleanup all threads...
            # TODO: check against args or init variables to None...
            if mitm_receiver_process is not None:
                logger.info("Trying to stop receiver")
                await mitm_receiver_process.shutdown()
                # logger.debug("MITM child threads successfully shutdown. Terminating parent thread")
                # mitm_receiver_process.()
                # logger.debug("Trying to join MITMReceiver")
                # mitm_receiver_process.join()
                #mitm_receiver_task.cancel()
                logger.debug("MITMReceiver joined")
           # if mitm_data_processor_manager is not None:
         #       await mitm_data_processor_manager.shutdown()
            if device_updater is not None:
                device_updater.stop_updater()
            if t_whw is not None:
                logger.info("Waiting for webhook-thread to exit")
                t_whw.cancel()
            if ws_server is not None:
                logger.info("Stopping websocket server")
                await ws_server.stop_server()
                logger.info("Waiting for websocket-thread to exit")
                # t_ws.cancel()
            if mapping_manager is not None:
                mapping_manager.shutdown()
            # if storage_manager is not None:
            #    logger.debug('Stopping storage manager')
            #    storage_manager.shutdown()
            if db_exec is not None:
                logger.debug("Calling db_pool_manager shutdown")
                # db_exec.shutdown()
                logger.debug("Done shutting down db_pool_manager")
        except Exception:
            logger.opt(exception=True).critical("An unhandled exception occurred during shutdown!")
        logger.info("Done shutting down")
        logger.debug(str(sys.exc_info()))
        sys.exit(exit_code)

if __name__ == "__main__":
    global application_args
    os.environ['LANGUAGE'] = application_args.language
    install_language()
    init_logging(application_args)
    logger = get_logger(LoggerEnums.system)

    loop = asyncio.get_event_loop()
    #signal.signal(signal.SIGINT, signal_handler)
    #signal.signal(signal.SIGTERM, signal_handler)

    loop_being_run = loop
    try:
        # loop.run_until_complete(start())
        asyncio.run(start(), debug=True)
    except (KeyboardInterrupt, Exception) as e:
        #shutdown(loop_being_run)
        logger.info(f"Shutting down. {e}")
        logger.exception(e)
