import sys
py_version = sys.version_info
if py_version.major < 3 or (py_version.major < 3 and py_version.minor < 6):
    print("MAD requires at least python 3.6! Your version: {}.{}"
          .format(py_version.major, py_version.minor))
    sys.exit(1)
from multiprocessing import Process
from typing import Optional

from utils.MappingManager import MappingManager, MappingManagerManager

import calendar
import datetime
import gc
import os
import pkg_resources
import time
from threading import Thread, active_count

import psutil

from db.DbFactory import DbFactory
from mitm_receiver.MitmMapper import MitmMapper, MitmMapperManager
from mitm_receiver.MITMReceiver import MITMReceiver
from utils.logging import initLogging, logger
from utils.madGlobals import terminate_mad
from utils.rarity import Rarity
from utils.version import MADVersion
from utils.walkerArgs import parseArgs
from websocket.WebsocketServer import WebsocketServer
from utils.updater import deviceUpdater

args = parseArgs()
os.environ['LANGUAGE'] = args.language
initLogging(args)


# Patch to make exceptions in threads cause an exception.
def install_thread_excepthook():
    """
    Workaround for sys.excepthook thread bug
    (https://sourceforge.net/tracker/?func=detail&atid=105470&aid=1230540&group_id=5470).
    Call once from __main__ before creating any threads.
    If using psyco, call psycho.cannotcompile(threading.Thread.run)
    since this replaces a new-style class method.
    """
    import sys
    run_thread_old = Thread.run
    run_process_old = Process.run

    def run_thread(*args, **kwargs):
        try:
            run_thread_old(*args, **kwargs)
        except (KeyboardInterrupt, SystemExit):
            raise
        except Exception:
            exc_type, exc_value, exc_trace = sys.exc_info()
            print(repr(sys.exc_info()))

            # Handle Flask's broken pipe when a client prematurely ends
            # the connection.
            if str(exc_value) == '[Errno 32] Broken pipe':
                pass
            else:
                logger.critical(
                    'Unhandled patched exception ({}): "{}".', exc_type, exc_value)
                sys.excepthook(exc_type, exc_value, exc_trace)

    def run_process(*args, **kwargs):
        try:
            run_process_old(*args, **kwargs)
        except (KeyboardInterrupt, SystemExit):
            raise
        except Exception:
            exc_type, exc_value, exc_trace = sys.exc_info()
            print(repr(sys.exc_info()))

            # Handle Flask's broken pipe when a client prematurely ends
            # the connection.
            if str(exc_value) == '[Errno 32] Broken pipe':
                pass
            else:
                logger.critical(
                    'Unhandled patched exception ({}): "{}".', exc_type, exc_value)
                sys.excepthook(exc_type, exc_value, exc_trace)
    Thread.run = run_thread
    Process.run = run_process


def generate_mappingjson():
    import json
    newfile = {}
    newfile['areas'] = []
    newfile['auth'] = []
    newfile['devices'] = []
    newfile['walker'] = []
    newfile['devicesettings'] = []
    with open(args.mappings, 'w') as outfile:
        json.dump(newfile, outfile, indent=4, sort_keys=True)


def find_referring_graphs(obj):
    REFERRERS_TO_IGNORE = [locals(), globals(), gc.garbage]

    referrers = (r for r in gc.get_referrers(obj)
                 if r not in REFERRERS_TO_IGNORE)
    for ref in referrers:
        if isinstance(ref, Graph):
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
        logger.info('Instance Name: "{}" - Memory usage: {} - CPU usage: {}',
                    str(args.status_name), str(memoryUse), str(cpuUse))
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
            logger.error("Some dependencies aren't met. Required: {} (Installed: {})", version_error.req, version_error.dist)
            sys.exit(1)


if __name__ == "__main__":
    check_dependencies()

    # TODO: globally destroy all threads upon sys.exit() for example
    install_thread_excepthook()

    db_wrapper, db_wrapper_manager = DbFactory.get_wrapper(args)
    db_wrapper.check_and_create_spawn_tables()
    db_wrapper.create_quest_database_if_not_exists()
    db_wrapper.create_status_database_if_not_exists()
    db_wrapper.create_usage_database_if_not_exists()
    db_wrapper.create_statistics_databases_if_not_exists()
    version = MADVersion(args, db_wrapper)
    version.get_version()

    # create folders
    create_folder(args.raidscreen_path)
    create_folder(args.file_path)
    create_folder(args.upload_path)

    if args.only_ocr:
        logger.error(
            "OCR scanning support has been dropped. Please get PogoDroid "
            "and scan using MITM methods."
        )
        sys.exit(1)

    if not args.only_scan and not args.only_routes:
        logger.error("No runmode selected. \nAllowed modes:\n"
                     " -os    ---- start scanner/devicecontroller\n"
                     " -or    ---- only calculate routes")
        sys.exit(1)

    mitm_receiver_process = None
    mitm_mapper_manager = None

    mapping_manager_manager = None
    mapping_manager: Optional[MappingManager] = None

    ws_server = None
    t_ws = None
    t_file_watcher = None
    t_whw = None

    if args.only_scan or args.only_routes:
        MappingManagerManager.register('MappingManager', MappingManager)
        mapping_manager_manager = MappingManagerManager()
        mapping_manager_manager.start()
        mapping_manager: MappingManager = mapping_manager_manager.MappingManager(db_wrapper, args, False)
        filename = args.mappings
        if not os.path.exists(filename):
            logger.error(
                "No mappings.json found - start madmin with with_madmin in config or copy example")
            sys.exit(1)

            logger.error(
                "No mappings.json found - starting setup mode with madmin.")
            logger.error("Open Madmin (ServerIP with Port " +
                         str(args.madmin_port) + ") - 'Mapping Editor' and restart.")
            generate_mappingjson()
        else:
            if args.only_routes:
                logger.info("Done calculating routes!")
                # TODO: shutdown managers properly...
                sys.exit(0)

            pogoWindowManager = None
            jobstatus: dict = {}
            MitmMapperManager.register('MitmMapper', MitmMapper)
            mitm_mapper_manager = MitmMapperManager()
            mitm_mapper_manager.start()
            mitm_mapper: MitmMapper = mitm_mapper_manager.MitmMapper(mapping_manager, db_wrapper)

            from ocr.pogoWindows import PogoWindows
            pogoWindowManager = PogoWindows(args.temp_path, args.ocr_thread_count)

            mitm_receiver_process = MITMReceiver(args.mitmreceiver_ip, int(args.mitmreceiver_port),
                                                 mitm_mapper, args, mapping_manager, db_wrapper)
            mitm_receiver_process.start()

            logger.info('Starting websocket server on port {}'.format(str(args.ws_port)))
            ws_server = WebsocketServer(args, mitm_mapper, db_wrapper, mapping_manager, pogoWindowManager)
            t_ws = Thread(name='scanner', target=ws_server.start_server)
            t_ws.daemon = False
            t_ws.start()

            # init jobprocessor
            device_Updater = deviceUpdater(ws_server, args, jobstatus)

            webhook_worker = None
            if args.webhook:
                from webhook.webhookworker import WebhookWorker

                rarity = Rarity(args, db_wrapper)
                rarity.start_dynamic_rarity()

                webhook_worker = WebhookWorker(
                    args, db_wrapper, mapping_manager, rarity)
                t_whw = Thread(name="webhook_worker",
                               target=webhook_worker.run_worker)
                t_whw.daemon = True
                t_whw.start()

    if args.statistic:
        if args.only_scan:
            logger.info("Starting statistics collector")
            t_usage = Thread(name='system',
                             target=get_system_infos, args=(db_wrapper,))
            t_usage.daemon = True
            t_usage.start()

    if args.with_madmin:
        from madmin.madmin import madmin_start

        logger.info("Starting Madmin on port {}", str(args.madmin_port))
        t_madmin = Thread(name="madmin", target=madmin_start,
                          args=(args, db_wrapper, ws_server, mapping_manager, device_Updater, jobstatus))
        t_madmin.daemon = True
        t_madmin.start()

    logger.info("Running.....")
    try:
        while True:
            time.sleep(10)
    except KeyboardInterrupt or Exception:
        logger.info("Shutdown signal received")
    finally:
        db_wrapper = None
        logger.success("Stop called")
        terminate_mad.set()
        # mitm_mapper.shutdown()

        # now cleanup all threads...
        # TODO: check against args or init variables to None...
        if t_whw is not None:
            t_whw.join()
        if ws_server is not None:
            ws_server.stop_server()
            t_ws.join()
        if mitm_receiver_process is not None:
            # mitm_receiver_thread.kill()
            logger.info("Trying to stop receiver")
            mitm_receiver_process.shutdown()
            mitm_receiver_process.terminate()
            logger.info("Trying to join MITMReceiver")
            mitm_receiver_process.join()
            logger.info("MITMReceiver joined")
            # mitm_receiver.stop_receiver()
            # mitm_receiver_thread.kill()
        # if t_file_watcher is not None:
        #     t_file_watcher.join()
        if mapping_manager_manager is not None:
            mapping_manager_manager.shutdown()
        # time.sleep(10)
        if mitm_mapper_manager is not None:
            # mitm_mapper.shutdown()
            logger.debug("Calling mitm_mapper shutdown")
            mitm_mapper_manager.shutdown()
        if db_wrapper_manager is not None:
            logger.debug("Calling db_wrapper shutdown")
            db_wrapper_manager.shutdown()
            logger.debug("Done shutting down db_wrapper")
        logger.debug("Done shutting down")
        logger.debug(str(sys.exc_info()))
        sys.exit(0)
