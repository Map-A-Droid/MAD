import calendar
import datetime
import gc
import glob
import os
import shutil
import sys
import time
from threading import Thread, active_count

import psutil
from db.monocleWrapper import MonocleWrapper
from db.rmWrapper import RmWrapper
from mitm_receiver.MitmMapper import MitmMapper
from mitm_receiver.MITMReceiver import MITMReceiver
from utils.logging import initLogging, logger
from utils.madGlobals import terminate_mad
from utils.mappingParser import MappingParser
from utils.rarity import Rarity
from utils.version import MADVersion
from utils.walkerArgs import parseArgs
from watchdog.observers import Observer
from websocket.WebsocketServer import WebsocketServer

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
    run_old = Thread.run

    def run(*args, **kwargs):
        try:
            run_old(*args, **kwargs)
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
    Thread.run = run


def start_ocr_observer(args, db_helper):
    from ocr.fileObserver import checkScreenshot
    observer = Observer()
    observer.schedule(checkScreenshot(args, db_helper),
                      path=args.raidscreen_path)
    observer.start()


def start_madmin(args, db_wrapper, ws_server):
    from madmin.madmin import madmin_start
    madmin_start(args, db_wrapper, ws_server)


def generate_mappingjson():
    import json
    newfile = {}
    newfile['areas'] = []
    newfile['auth'] = []
    newfile['devices'] = []
    newfile['walker'] = []
    newfile['devicesettings'] = []
    with open('configs/mappings.json', 'w') as outfile:
        json.dump(newfile, outfile, indent=4, sort_keys=True)


def file_watcher(db_wrapper, mitm_mapper, ws_server, webhook_worker):
    # We're on a 60-second timer.
    refresh_time_sec = 60
    filename = 'configs/mappings.json'

    while not terminate_mad.is_set():
        # Wait (x-1) seconds before refresh, min. 1s.
        time.sleep(max(1, refresh_time_sec - 1))
        try:
            # Only refresh if the file has changed.
            current_time_sec = time.time()
            file_modified_time_sec = os.path.getmtime(filename)
            time_diff_sec = current_time_sec - file_modified_time_sec

            # File has changed in the last refresh_time_sec seconds.
            if time_diff_sec < refresh_time_sec:
                logger.info(
                    'Change found in {}. Updating device mappings.', filename)
                (device_mappings, routemanagers, auths) = load_mappings(db_wrapper)
                mitm_mapper._device_mappings = device_mappings
                logger.info('Propagating new mappings to all clients.')
                ws_server.update_settings(
                    routemanagers, device_mappings, auths)

                if webhook_worker is not None:
                    webhook_worker.update_settings(routemanagers)
            else:
                logger.debug('No change found in {}.', filename)
        except Exception as e:
            logger.exception(
                'Exception occurred while updating device mappings: {}.', e)


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

    while not terminate_mad.is_set():
        logger.info('Starting internal Cleanup')
        logger.debug('Collecting...')
        n = gc.collect()
        logger.info('Unreachable objects: {} - Remaining garbage: {} - Running threads: {}',
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
            logger.info("Garbage collector: collected %d objects." % collected)
        zero = datetime.datetime.utcnow()
        unixnow = calendar.timegm(zero.utctimetuple())
        db_wrapper.insert_usage(args.status_name, cpuUse,
                                memoryUse, collected, unixnow)
        time.sleep(args.statistic_interval)


def create_folder(folder):
    if not os.path.exists(folder):
        logger.info(str(folder) + ' created')
        os.makedirs(folder)


def load_mappings(db_wrapper):
    mapping_parser = MappingParser(db_wrapper, args, configmode=False)
    device_mappings = mapping_parser.get_devicemappings()
    routemanagers = mapping_parser.get_routemanagers()
    auths = mapping_parser.get_auths()
    return (device_mappings, routemanagers, auths)


if __name__ == "__main__":
    # TODO: globally destroy all threads upon sys.exit() for example
    install_thread_excepthook()

    if args.db_method == "rm":
        db_wrapper = RmWrapper(args)
    elif args.db_method == "monocle":
        db_wrapper = MonocleWrapper(args)
    else:
        logger.error("Invalid db_method in config. Exiting")
        sys.exit(1)
    db_wrapper.create_hash_database_if_not_exists()
    db_wrapper.check_and_create_spawn_tables()
    db_wrapper.create_quest_database_if_not_exists()
    db_wrapper.create_status_database_if_not_exists()
    db_wrapper.create_usage_database_if_not_exists()
    version = MADVersion(args, db_wrapper)
    version.get_version()

    if args.clean_hash_database:
        logger.info('Cleanup Hash Database and www_hash folder')
        db_wrapper.delete_hash_table('999', '')
        for file in glob.glob("ocr/www_hash/*.jpg"):
            os.remove(file)
        sys.exit(0)

    # create folders
    create_folder(args.raidscreen_path)
    create_folder(args.file_path)

    if not args.only_scan and not args.with_madmin and not args.only_ocr and not args.only_routes:
        logger.error("No runmode selected. \nAllowed modes:\n"
                     " -wm    ---- start madmin (browserbased monitoring/configuration)\n"
                     " -os    ---- start scanner/devicecontroller\n"
                     " -oo    ---- start OCR analysis of screenshots\n"
                     " -or    ---- only calculate routes")
        sys.exit(1)

    t_mitm = None
    mitm_receiver = None
    ws_server = None
    t_ws = None
    t_file_watcher = None
    t_whw = None

    if args.only_scan or args.only_routes:

        filename = os.path.join('configs', 'mappings.json')
        if not os.path.exists(filename):
            if not args.with_madmin:
                logger.error(
                    "No mappings.json found - start madmin with with_madmin in config or copy example")
                sys.exit(1)

            logger.error(
                "No mappings.json found - starting setup mode with madmin.")
            logger.error("Open Madmin (ServerIP with Port " +
                         str(args.madmin_port) + ") - 'Mapping Editor' and restart.")
            generate_mappingjson()
        else:

            try:
                (device_mappings, routemanagers, auths) = load_mappings(db_wrapper)
            except KeyError as e:
                logger.error(
                    "Could not parse mappings. Please check those. Reason: {}", str(e))
                sys.exit(1)
            except RuntimeError as e:
                logger.error(
                    "There is something wrong with your mappings. Reason: {}", str(e))
                sys.exit(1)

            if args.only_routes:
                logger.info("Done calculating routes!")
                sys.exit(0)

            pogoWindowManager = None

            mitm_mapper = MitmMapper(device_mappings)
            ocr_enabled = False

            for routemanager in routemanagers.keys():
                area = routemanagers.get(routemanager, None)
                if area is None:
                    continue
                if "ocr" in area.get("mode", ""):
                    ocr_enabled = True
                if ("ocr" in area.get("mode", "") or "pokestop" in area.get("mode", "")) and args.no_ocr:
                    logger.error(
                        'No-OCR Mode is activated - No OCR Mode possible.')
                    logger.error(
                        'Check your config.ini and be sure that CV2 and Tesseract is installed')
                    sys.exit(1)

            if not args.no_ocr:
                from ocr.pogoWindows import PogoWindows
                pogoWindowManager = PogoWindows(args.temp_path)

            if ocr_enabled:
                from ocr.copyMons import MonRaidImages
                MonRaidImages.runAll(args.pogoasset, db_wrapper=db_wrapper)

            mitm_receiver = MITMReceiver(args.mitmreceiver_ip, int(args.mitmreceiver_port),
                                         mitm_mapper, args, auths, db_wrapper)
            t_mitm = Thread(name='mitm_receiver',
                            target=mitm_receiver.run_receiver)
            t_mitm.daemon = True
            t_mitm.start()
            time.sleep(5)

            logger.info('Starting scanner')
            ws_server = WebsocketServer(args, mitm_mapper, db_wrapper,
                                        routemanagers, device_mappings, auths, pogoWindowManager)
            t_ws = Thread(name='scanner', target=ws_server.start_server)
            t_ws.daemon = False
            t_ws.start()

            webhook_worker = None
            if args.webhook:
                from webhook.webhookworker import WebhookWorker

                rarity = Rarity(args, db_wrapper)
                rarity.start_dynamic_rarity()

                webhook_worker = WebhookWorker(
                    args, db_wrapper, routemanagers, rarity)
                t_whw = Thread(name="webhook_worker",
                               target=webhook_worker.run_worker)
                t_whw.daemon = False
                t_whw.start()

            logger.info("Starting file watcher for mappings.json changes.")
            t_file_watcher = Thread(name='file_watcher', target=file_watcher,
                                    args=(db_wrapper, mitm_mapper, ws_server, webhook_worker))
            t_file_watcher.daemon = False
            t_file_watcher.start()

    if args.only_ocr:
        from ocr.copyMons import MonRaidImages

        MonRaidImages.runAll(args.pogoasset, db_wrapper=db_wrapper)

        logger.info('Starting OCR worker')
        t_observ = Thread(
            name='observer', target=start_ocr_observer, args=(args, db_wrapper,))
        t_observ.daemon = True
        t_observ.start()

    if args.with_madmin:
        logger.info('Starting Madmin on Port: {}', str(args.madmin_port))
        t_flask = Thread(name='madmin', target=start_madmin,
                         args=(args, db_wrapper, ws_server,))
        t_flask.daemon = True
        t_flask.start()

    if args.statistic:
        if args.only_ocr or args.only_scan:
            t_usage = Thread(name='system',
                             target=get_system_infos, args=(db_wrapper,))
            t_usage.daemon = False
            t_usage.start()

    try:
        while True:
            time.sleep(10)
    finally:
        db_wrapper = None
        logger.success("Stop called")
        terminate_mad.set()
        # now cleanup all threads...
        # TODO: check against args or init variables to None...
        if t_whw is not None:
            t_whw.join()
        if t_mitm is not None and mitm_receiver is not None:
            mitm_receiver.stop_receiver()
        if ws_server is not None:
            ws_server.stop_server()
            t_ws.join()
        if t_file_watcher is not None:
            t_file_watcher.join()
        sys.exit(0)
