import asyncio
import calendar
import datetime
import gc
import os
import sys
import time
from multiprocessing import Process
from threading import Thread, active_count
from typing import Optional

import pkg_resources
import psutil

from mapadroid.db.DbFactory import DbFactory

# TODO: Get MADmin running
# from mapadroid.madmin.madmin import MADmin
from mapadroid.mad_apk.abstract_apk_storage import AbstractAPKStorage
from mapadroid.mitm_receiver.MitmDataProcessorManager import \
    MitmDataProcessorManager
from mapadroid.mitm_receiver.MitmMapper import MitmMapper
from mapadroid.mitm_receiver.MITMReceiver import MITMReceiver
from mapadroid.ocr.pogoWindows import PogoWindows
from mapadroid.utils.event import Event
from mapadroid.utils.logging import LoggerEnums, get_logger, init_logging
from mapadroid.utils.madGlobals import terminate_mad
from mapadroid.mapping_manager.MappingManager import MappingManager
# from mapadroid.utils.pluginBase import PluginCollection
from mapadroid.utils.rarity import Rarity
from mapadroid.utils.updater import DeviceUpdater
from mapadroid.utils.walkerArgs import parse_args
from mapadroid.webhook.webhookworker import WebhookWorker
from mapadroid.websocket.WebsocketServer import WebsocketServer

py_version = sys.version_info
if py_version.major < 3 or (py_version.major == 3 and py_version.minor < 6):
    print("MAD requires at least python 3.6! Your version: {}.{}"
          .format(py_version.major, py_version.minor))
    sys.exit(1)


# Patch to make exceptions in threads cause an exception.
def install_thread_excepthook():
    """
    Workaround for sys.excepthook thread bug
    (https://sourceforge.net/tracker/?func=detail&atid=105470&aid=1230540&group_id=5470).
    Call once from __main__ before creating any threads.
    If using psyco, call psycho.cannotcompile(threading.Thread.run)
    since this replaces a new-style class method.
    """
    run_thread_old = Thread.run
    run_process_old = Process.run

    def run_thread(*args, **kwargs):
        try:
            run_thread_old(*args, **kwargs)
        except (KeyboardInterrupt, SystemExit):
            raise
        except BrokenPipeError:
            pass
        except Exception:
            logger.opt(exception=True).critical("An unhanded exception occurred!")

    def run_process(*args, **kwargs):
        try:
            run_process_old(*args, **kwargs)
        except (KeyboardInterrupt, SystemExit):
            raise
        except BrokenPipeError:
            pass
        except Exception:
            logger.opt(exception=True).critical("An unhanded exception occurred!")

    Thread.run = run_thread
    Process.run = run_process


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


def get_system_infos(db_wrapper):
    pid = os.getpid()
    py = psutil.Process(pid)
    gc.set_threshold(5, 1, 1)
    gc.enable()

    while not terminate_mad.is_set():
        logger.debug('Starting internal Cleanup')
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
                    str(args.status_name), mem_usage, str(cpu_usage))
        collected = None
        if args.stat_gc:
            collected = gc.collect()
            logger.debug("Garbage collector: collected %d objects." % collected)
        zero = datetime.datetime.utcnow()
        unixnow = calendar.timegm(zero.utctimetuple())
        db_wrapper.insert_usage(args.status_name, cpu_usage, mem_usage, collected, unixnow)
        time.sleep(args.statistic_interval)


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
    event: Event = None
    jobstatus: dict = {}
    # mapping_manager_manager: MappingManagerManager = None
    mapping_manager: Optional[MappingManager] = None
    mitm_receiver_process: MITMReceiver = None
    mitm_mapper: Optional[MitmMapper] = None
    pogo_win_manager: Optional[PogoWindows] = None
    storage_elem: Optional[AbstractAPKStorage] = None
    # storage_manager: Optional[StorageSyncManager] = None
    t_whw: Thread = None  # Thread for WebHooks
    t_ws: Thread = None  # Thread - WebSocket Server
    webhook_worker: Optional[WebhookWorker] = None
    ws_server: WebsocketServer = None
    if args.config_mode:
        logger.info('Starting MAD in config mode')
    else:
        logger.info('Starting MAD')
    # check_dependencies()
    # TODO: globally destroy all threads upon sys.exit() for example
    install_thread_excepthook()
    create_folder(args.file_path)
    create_folder(args.upload_path)
    create_folder(args.temp_path)
    if args.config_mode and args.only_routes:
        logger.error('Unable to run with config_mode and only_routes.  Only use one option')
        sys.exit(1)
    if not args.only_scan and not args.only_routes:
        logger.error("No runmode selected. \nAllowed modes:\n"
                     " -os    ---- start scanner/devicecontroller\n"
                     " -or    ---- only calculate routes")
        sys.exit(1)
    # Elements that should initialized regardless of the functionality being used
    db_wrapper, db_exec = DbFactory.get_wrapper(args)
    await db_exec.setup()
    await db_wrapper.setup()

    # TODO: MADPatcher(args, data_manager)
    #  data_manager.clear_on_boot()
    #  data_manager.fix_routecalc_on_boot()
    event = Event(args, db_wrapper)
    await event.start_event_checker()
    # Do not remove this sleep unless you have solved the race condition on boot with the logger
    await asyncio.sleep(.1)
    # MappingManagerManager.register('MappingManager', MappingManager)
    # mapping_manager_manager = MappingManagerManager()
    # mapping_manager_manager.start()
    mapping_manager: MappingManager = MappingManager(db_wrapper,
                                                     args,
                                                     configmode=args.config_mode)
    await mapping_manager.setup()
    # TODO: Call init of mapping_manager properly rather than in constructor...

    if args.only_routes:
        logger.info('Running in route recalculation mode. MAD will exit once complete')
        recalc_in_progress = True
        while recalc_in_progress:
            time.sleep(5)
            sql = "SELECT COUNT(*) > 0 FROM `settings_routecalc` WHERE `recalc_status` = 1"
            # TODO recalc_in_progress = db_wrapper.autofetch_value(sql)
        logger.info("Done calculating routes!")
        # TODO: shutdown managers properly...
        sys.exit(0)
    # (storage_manager, storage_elem) = get_storage_obj(args, db_wrapper)
    if not args.config_mode:
        pogo_win_manager = PogoWindows(args.temp_path, args.ocr_thread_count)
        mitm_mapper = MitmMapper(args, mapping_manager, db_wrapper.stats_submit)
        await mitm_mapper.init()
    logger.info('Starting PogoDroid Receiver server on port {}'.format(str(args.mitmreceiver_port)))

    # TODO: Enable and properly integrate...
    mitm_data_processor_manager = MitmDataProcessorManager(args, mitm_mapper, db_wrapper)
    await mitm_data_processor_manager.launch_processors()

    mitm_receiver = MITMReceiver(args.mitmreceiver_ip, int(args.mitmreceiver_port),
                                         mitm_mapper, args, mapping_manager, db_wrapper,
                                         None,
                                         mitm_data_processor_manager.get_queue(),
                                         enable_configmode=args.config_mode)
    mitm_receiver_task = await mitm_receiver.run_async()
    logger.info('Starting websocket server on port {}'.format(str(args.ws_port)))
    ws_server = WebsocketServer(args=args,
                                mitm_mapper=mitm_mapper,
                                db_wrapper=db_wrapper,
                                mapping_manager=mapping_manager,
                                pogo_window_manager=pogo_win_manager,
                                event=event,
                                enable_configmode=args.config_mode)
    # t_ws = Thread(name='system', target=ws_server.start_server)
    # t_ws.daemon = False
    # t_ws.start()
    await ws_server.start_server()

    #device_updater = DeviceUpdater(ws_server, args, jobstatus, db_wrapper, storage_elem)
    #await device_updater.init_jobs()
    #if not args.config_mode:
    #    if args.webhook:
    #        rarity = Rarity(args, db_wrapper)
    #        rarity.start_dynamic_rarity()
    #        webhook_worker = WebhookWorker(args, db_wrapper, mapping_manager, rarity, db_wrapper.webhook_reader)
    #        # TODO: Start webhook_worker task
            # t_whw = Thread(name="system",
   #         #               target=webhook_worker.run_worker)
            #t_whw.daemon = True
  #          #t_whw.start()
  #      if args.statistic:
  #          logger.info("Starting statistics collector")
  #          t_usage = Thread(name='system',
  #                           target=get_system_infos, args=(db_wrapper,))
  #          t_usage.daemon = True
  #          t_usage.start()

    # madmin = MADmin(args, db_wrapper, ws_server, mapping_manager, device_updater, jobstatus, storage_elem)

    # starting plugin system
    plugin_parts = {
        'args': args,
        'db_wrapper': db_wrapper,
        'device_Updater': device_updater,
        'event': event,
        'jobstatus': jobstatus,
        'logger': get_logger(LoggerEnums.plugin),
        # 'madmin': madmin,
        'mapping_manager': mapping_manager,
        'mitm_mapper': mitm_mapper,
        'mitm_receiver_process': mitm_receiver_process,
        # 'storage_elem': storage_elem,
        'webhook_worker': webhook_worker,
        'ws_server': ws_server,
    #    'mitm_data_processor_manager': mitm_data_processor_manager
    }
    # TODO: Restore functionality
    # mad_plugins = PluginCollection('plugins', plugin_parts)
    # mad_plugins.apply_all_plugins_on_value()

    # if not args.disable_madmin or args.config_mode:
    #     logger.info("Starting Madmin on port {}", str(args.madmin_port))
     #   t_madmin = Thread(name="madmin", target=madmin.madmin_start)
     #   t_madmin.daemon = True
     #   t_madmin.start()

    logger.info("MAD is now running.....")
    exit_code = 0
    device_creator = None
    try:
        if args.unit_tests:
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
    except KeyboardInterrupt or Exception:
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
                mitm_receiver_process.shutdown()
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
                t_whw.join()
            if ws_server is not None:
                logger.info("Stopping websocket server")
                await ws_server.stop_server()
                logger.info("Waiting for websocket-thread to exit")
                t_ws.join()
            if mapping_manager is not None:
                mapping_manager.shutdown()
            # if storage_manager is not None:
            #    logger.debug('Stopping storage manager')
            #    storage_manager.shutdown()
            if db_exec is not None:
                logger.debug("Calling db_pool_manager shutdown")
                db_exec.shutdown()
                logger.debug("Done shutting down db_pool_manager")
        except Exception:
            logger.opt(exception=True).critical("An unhanded exception occurred during shutdown!")
        logger.info("Done shutting down")
        logger.debug(str(sys.exc_info()))
        sys.exit(exit_code)

if __name__ == "__main__":
    args = parse_args()
    os.environ['LANGUAGE'] = args.language
    init_logging(args)
    logger = get_logger(LoggerEnums.system)

    loop = asyncio.get_event_loop()
    #signal.signal(signal.SIGINT, signal_handler)
    #signal.signal(signal.SIGTERM, signal_handler)

    loop_being_run = loop
    try:
        loop.run_until_complete(start())
    except (KeyboardInterrupt, Exception) as e:
        #shutdown(loop_being_run)
        logger.info(f"Shutting down. {e}")
