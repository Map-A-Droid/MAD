import sys

py_version = sys.version_info
if py_version.major < 3 or (py_version.major == 3 and py_version.minor < 6):
    print("MAD requires at least python 3.6! Your version: {}.{}"
          .format(py_version.major, py_version.minor))
    sys.exit(1)
from multiprocessing import Process
from typing import Optional
import calendar
import datetime
import gc
import os
import pkg_resources
import time
from threading import Thread, active_count
import psutil
from mapadroid.utils.MappingManager import MappingManager, MappingManagerManager
from mapadroid.db.DbFactory import DbFactory
from mapadroid.mitm_receiver.MitmMapper import MitmMapper, MitmMapperManager
from mapadroid.mitm_receiver.MITMReceiver import MITMReceiver
from mapadroid.utils.madGlobals import terminate_mad
from mapadroid.utils.rarity import Rarity
from mapadroid.utils.event import Event
from mapadroid.patcher import MADPatcher
from mapadroid.utils.walkerArgs import parseArgs
from mapadroid.websocket.WebsocketServer import WebsocketServer
from mapadroid.utils.updater import deviceUpdater
from mapadroid.data_manager import DataManager
from mapadroid.ocr.pogoWindows import PogoWindows
from mapadroid.webhook.webhookworker import WebhookWorker
from mapadroid.mad_apk import get_storage_obj, StorageSyncManager, AbstractAPKStorage
from mapadroid.madmin.madmin import madmin
from mapadroid.utils.pluginBase import PluginCollection
import unittest
from mapadroid.utils.logging import initLogging, get_logger, LoggerEnums


args = parseArgs()
os.environ['LANGUAGE'] = args.language
initLogging(args)
logger = get_logger(LoggerEnums.system)


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
    REFERRERS_TO_IGNORE = [locals(), globals(), gc.garbage]

    referrers = (r for r in gc.get_referrers(obj)
                 if r not in REFERRERS_TO_IGNORE)
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
        n = gc.collect()
        logger.debug('Unreachable objects: {} - Remaining garbage: {} - Running threads: {}',
                     str(n), str(gc.garbage), str(active_count()))

        for obj in gc.garbage:
            for ref in find_referring_graphs(obj):
                ref.set_next(None)
                del ref  # remove local reference so the node can be deleted
            del obj  # remove local reference so the node can be deleted

        # Clear references held by gc.garbage
        logger.debug('Clearing gc garbage')
        del gc.garbage[:]

        memoryUse = py.memory_info()[0] / 2. ** 30
        cpuUse = py.cpu_percent()
        logger.info('Instance name: "{}" - Memory usage: {:.3f} GB - CPU usage: {}',
                    str(args.status_name), memoryUse, str(cpuUse))
        collected = None
        if args.stat_gc:
            collected = gc.collect()
            logger.debug("Garbage collector: collected %d objects." % collected)
        zero = datetime.datetime.utcnow()
        unixnow = calendar.timegm(zero.utctimetuple())
        db_wrapper.insert_usage(args.status_name, cpuUse,
                                memoryUse, collected, unixnow)
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


if __name__ == "__main__":
    data_manager: DataManager = None
    device_Updater: deviceUpdater = None
    event: Event = None
    jobstatus: dict = {}
    mapping_manager_manager: MappingManagerManager = None
    mapping_manager: Optional[MappingManager] = None
    mitm_receiver_process: MITMReceiver = None
    mitm_mapper_manager: Optional[MitmMapperManager] = None
    mitm_mapper: Optional[MitmMapper] = None
    pogoWindowManager: Optional[PogoWindows] = None
    storage_elem: Optional[AbstractAPKStorage] = None
    storage_manager: Optional[StorageSyncManager] = None
    t_whw: Thread = None  # Thread for WebHooks
    t_ws: Thread = None  # Thread - WebSocket Server
    webhook_worker: Optional[WebhookWorker] = None
    ws_server: WebsocketServer = None
    if args.config_mode:
        logger.info('Starting MAD in config mode')
    else:
        logger.info('Starting MAD')
    check_dependencies()
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
    db_wrapper, db_pool_manager = DbFactory.get_wrapper(args)
    try:
        instance_id = db_wrapper.get_instance_id()
    except Exception:
        instance_id = None
    data_manager = DataManager(db_wrapper, instance_id)
    MADPatcher(args, data_manager)
    data_manager.clear_on_boot()
    data_manager.fix_routecalc_on_boot()
    event = Event(args, db_wrapper)
    event.start_event_checker()
    # Do not remove this sleep unless you have solved the race condition on boot with the logger
    time.sleep(.1)
    MappingManagerManager.register('MappingManager', MappingManager)
    mapping_manager_manager = MappingManagerManager()
    mapping_manager_manager.start()
    mapping_manager: MappingManager = mapping_manager_manager.MappingManager(db_wrapper,
                                                                             args,
                                                                             data_manager,
                                                                             configmode=args.config_mode)
    if args.only_routes:
        logger.info('Running in route recalculation mode.  MAD will exit once complete')
        recalc_in_progress = True
        while recalc_in_progress:
            time.sleep(5)
            sql = "SELECT COUNT(*) > 0 FROM `settings_routecalc` WHERE `recalc_status` = 1"
            recalc_in_progress = db_wrapper.autofetch_value(sql)
        logger.info("Done calculating routes!")
        # TODO: shutdown managers properly...
        sys.exit(0)
    (storage_manager, storage_elem) = get_storage_obj(args, db_wrapper)
    if not args.config_mode:
        pogoWindowManager = PogoWindows(args.temp_path, args.ocr_thread_count)
        MitmMapperManager.register('MitmMapper', MitmMapper)
        mitm_mapper_manager = MitmMapperManager()
        mitm_mapper_manager.start()
        mitm_mapper = mitm_mapper_manager.MitmMapper(mapping_manager, db_wrapper.stats_submit)
    logger.info('Starting PogoDroid Receiver server on port {}'.format(str(args.mitmreceiver_port)))
    mitm_receiver_process = MITMReceiver(args.mitmreceiver_ip, int(args.mitmreceiver_port),
                                         mitm_mapper, args, mapping_manager, db_wrapper,
                                         data_manager,
                                         storage_elem,
                                         enable_configmode=args.config_mode)
    mitm_receiver_process.start()
    logger.info('Starting websocket server on port {}'.format(str(args.ws_port)))
    ws_server = WebsocketServer(args=args,
                                mitm_mapper=mitm_mapper,
                                db_wrapper=db_wrapper,
                                mapping_manager=mapping_manager,
                                pogo_window_manager=pogoWindowManager,
                                data_manager=data_manager,
                                event=event,
                                enable_configmode=args.config_mode)
    t_ws = Thread(name='system', target=ws_server.start_server)
    t_ws.daemon = False
    t_ws.start()
    device_Updater = deviceUpdater(ws_server, args, jobstatus, db_wrapper, storage_elem)
    if not args.config_mode:
        if args.webhook:
            rarity = Rarity(args, db_wrapper)
            rarity.start_dynamic_rarity()
            webhook_worker = WebhookWorker(
                args, data_manager, mapping_manager, rarity, db_wrapper.webhook_reader)
            t_whw = Thread(name="system",
                           target=webhook_worker.run_worker)
            t_whw.daemon = True
            t_whw.start()
        if args.statistic:
            logger.info("Starting statistics collector")
            t_usage = Thread(name='system',
                             target=get_system_infos, args=(db_wrapper,))
            t_usage.daemon = True
            t_usage.start()

    madmin = madmin(args, db_wrapper, ws_server, mapping_manager, data_manager, device_Updater, jobstatus, storage_elem)

    # starting plugin system
    plugin_parts = {
        'args': args,
        'data_manager': data_manager,
        'db_wrapper': db_wrapper,
        'device_Updater': device_Updater,
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
    }
    mad_plugins = PluginCollection('plugins', plugin_parts)
    mad_plugins.apply_all_plugins_on_value()

    if args.with_madmin or args.config_mode:
        logger.info("Starting Madmin on port {}", str(args.madmin_port))
        t_madmin = Thread(name="madmin", target=madmin.madmin_start)
        t_madmin.daemon = True
        t_madmin.start()

    logger.info("MAD is now running.....")
    exit_code = 0
    device_creator = None
    try:
        if args.unit_tests:
            from mapadroid.tests.local_api import LocalAPI
            api_ready = False
            api = LocalAPI()
            logger.info('Checking API status')
            if not data_manager.get_root_resource('device').keys():
                from mapadroid.tests.test_utils import ResourceCreator
                logger.info('Creating a device')
                device_creator = ResourceCreator(api, prefix='MADCore')
                res = device_creator.create_valid_resource('device')[0]
                mapping_manager.update()
            while not api_ready:
                try:
                    api.get('/api')
                    api_ready = True
                    logger.info('API is ready for unit testing')
                except Exception:
                    time.sleep(1)
            loader = unittest.TestLoader()
            start_dir = 'mapadroid/tests/'
            suite = loader.discover(start_dir)
            runner = unittest.TextTestRunner()
            result = runner.run(suite)
            exit_code = 0 if result.wasSuccessful() else 1
            raise KeyboardInterrupt
        else:
            while True:
                time.sleep(10)
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
                # mitm_receiver_thread.kill()
                logger.info("Trying to stop receiver")
                mitm_receiver_process.shutdown()
                logger.debug("MITM child threads successfully shutdown.  Terminating parent thread")
                mitm_receiver_process.terminate()
                logger.debug("Trying to join MITMReceiver")
                mitm_receiver_process.join()
                logger.debug("MITMReceiver joined")
            if device_Updater is not None:
                device_Updater.stop_updater()
            if t_whw is not None:
                logger.info("Waiting for webhook-thread to exit")
                t_whw.join()
            if ws_server is not None:
                logger.info("Stopping websocket server")
                ws_server.stop_server()
                logger.info("Waiting for websocket-thread to exit")
                t_ws.join()
            if mapping_manager_manager is not None:
                mapping_manager_manager.shutdown()
            if mitm_mapper_manager is not None:
                logger.debug("Calling mitm_mapper shutdown")
                mitm_mapper_manager.shutdown()
            if storage_manager is not None:
                logger.debug('Stopping storage manager')
                storage_manager.shutdown()
            if db_pool_manager is not None:
                logger.debug("Calling db_pool_manager shutdown")
                db_pool_manager.shutdown()
                logger.debug("Done shutting down db_pool_manager")
        except Exception:
            logger.opt(exception=True).critical("An unhanded exception occurred during shutdown!")
        logger.info("Done shutting down")
        logger.debug(str(sys.exc_info()))
        sys.exit(exit_code)
