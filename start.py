import glob
import logging
import os
import sys
import time
import psutil
from threading import Thread, active_count
import datetime
import calendar
import gc

from colorlog import ColoredFormatter
from logging.handlers import RotatingFileHandler
from watchdog.observers import Observer

from db.monocleWrapper import MonocleWrapper
from db.rmWrapper import RmWrapper
from mitm_receiver.MitmMapper import MitmMapper
from mitm_receiver.MITMReceiver import MITMReceiver
from utils.madGlobals import terminate_mad
from utils.mappingParser import MappingParser
from utils.walkerArgs import parseArgs
from utils.webhookHelper import WebhookHelper
from utils.version import MADVersion
from websocket.WebsocketServer import WebsocketServer

log = logging.getLogger()
args = parseArgs()
os.environ['LANGUAGE'] = args.language


class LogFilter(logging.Filter):
    def __init__(self, level):
        super().__init__()
        self.level = level

    def filter(self, record):
        return record.levelno < self.level


def handle_exception(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return

    log.error("Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback))


sys.excepthook = handle_exception


def set_log_and_verbosity(log):
    formatter = ColoredFormatter(
        '%(log_color)s [%(asctime)s] [%(threadName)16s] [%(module)14s:%(lineno)d]' +
        ' [%(levelname)8s] %(message)s',
        datefmt='%m-%d %H:%M:%S',
        reset=True,
        log_colors={
            'DEBUG': 'purple',
            'INFO': 'cyan',
            'WARNING': 'yellow',
            'ERROR': 'red',
            'CRITICAL': 'red,bg_white',
        },
        secondary_log_colors={},
        style='%'
    )

    # Redirect messages lower than WARNING to stdout
    stdout_hdlr = logging.StreamHandler(sys.stdout)
    stdout_hdlr.setFormatter(formatter)
    log_filter = LogFilter(logging.WARNING)
    stdout_hdlr.addFilter(log_filter)
    stdout_hdlr.setLevel(5)

    # Redirect messages equal or higher than WARNING to stderr
    stderr_hdlr = logging.StreamHandler(sys.stderr)
    stderr_hdlr.setFormatter(formatter)
    stderr_hdlr.setLevel(logging.WARNING)

    log.addHandler(stdout_hdlr)
    log.addHandler(stderr_hdlr)

    if not args.no_file_logs:
        # Create directory for log files.
        if not os.path.exists(args.log_path):
            os.mkdir(args.log_path)

        filename = os.path.join(args.log_path, args.log_filename)
        if not args.log_rotation:
            filelog = logging.FileHandler(filename)
        else:
            filelog = RotatingFileHandler(filename, maxBytes=args.log_rotation_file_size,
                                          backupCount=args.log_rotation_backup_count)
        filelog.setFormatter(logging.Formatter(
            '%(asctime)s [%(threadName)18s][%(module)14s:%(lineno)d][%(levelname)8s] ' +
            '%(message)s'))
        log.addHandler(filelog)

    if args.verbose:
        log.setLevel(logging.DEBUG)
    else:
        log.setLevel(logging.INFO)


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
                log.critical('Unhandled patched exception (%s): "%s".',
                             exc_type, exc_value)
                sys.excepthook(exc_type, exc_value, exc_trace)
    Thread.run = run


def start_ocr_observer(args, db_helper):
    from ocr.fileObserver import checkScreenshot
    observer = Observer()
    log.error(args.raidscreen_path)
    observer.schedule(checkScreenshot(args, db_helper), path=args.raidscreen_path)
    observer.start()


def delete_old_logs(minutes):
    if minutes == 0:
        log.info('delete_old_logs: Search/Delete logs is disabled')
        return

    while not terminate_mad.is_set():
        log.info('delete_old_logs: Search/Delete logs older than ' + str(minutes) + ' minutes')

        now = time.time()

        logpath = args.log_path

        log.debug('delete_old_logs: Log Folder: ' + str(logpath))
        for file in os.listdir(logpath):
            file_full_path = os.path.join(logpath, file)
            if os.path.isfile(file_full_path):
                # Delete files older than x days
                if os.stat(file_full_path).st_mtime < now - int(minutes) * 60:
                    os.remove(file_full_path)
                    log.info('delete_old_logs: File Removed : ' + file_full_path)

        log.info('delete_old_logs: Search/Delete logs finished')
        time.sleep(3600)


def start_madmin(args, db_wrapper):
    from madmin.madmin import madmin_start
    madmin_start(args, db_wrapper)


def generate_mappingjson():
    import json
    newfile = {}
    newfile['areas'] = []
    newfile['auth'] = []
    newfile['devices'] = []
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
                log.info(
                    'Change found in %s. Updating device mappings.', filename)
                (device_mappings, routemanagers, auths) = load_mappings(db_wrapper)
                mitm_mapper._device_mappings = device_mappings
                log.info('Propagating new mappings to all clients.')
                ws_server.update_settings(
                    routemanagers, device_mappings, auths)

                if webhook_worker is not None:
                    webhook_worker.update_settings(routemanagers)
            else:
                log.debug('No change found in %s.', filename)
        except Exception as e:
            log.exception(
                'Exception occurred while updating device mappings: %s.', e)


def find_referring_graphs(obj):
    REFERRERS_TO_IGNORE = [locals(), globals(), gc.garbage]

    print('Looking for references to %s' % repr(obj))
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
        log.info('Starting internal Cleanup')
        log.debug('Collecting...')
        n = gc.collect()
        log.info('Unreachable objects: %s - Remaining garbage: %s - Running threads: %s' % (str(n), str(gc.garbage), str(active_count())))

        for obj in gc.garbage:
            for ref in find_referring_graphs(obj):
                ref.set_next(None)
                del ref  # remove local reference so the node can be deleted
            del obj  # remove local reference so the node can be deleted

        # Clear references held by gc.garbage
        log.debug('Clearing gc garbage')
        del gc.garbage[:]

        memoryUse = py.memory_info()[0] / 2. ** 30
        cpuUse = py.cpu_percent()
        log.info('Instance Name: "%s" - Memory usage: %s - CPU usage: %s' % (str(args.status_name), str(memoryUse), str(cpuUse)))
        collected = None
        if args.stat_gc:
            collected = gc.collect()
            log.info("Garbage collector: collected %d objects." % collected)
        zero = datetime.datetime.utcnow()
        unixnow = calendar.timegm(zero.utctimetuple())
        db_wrapper.insert_usage(args.status_name, cpuUse, memoryUse, collected, unixnow)
        time.sleep(args.statistic_interval)


def load_mappings(db_wrapper):
    mapping_parser = MappingParser(db_wrapper)
    device_mappings = mapping_parser.get_devicemappings()
    routemanagers = mapping_parser.get_routemanagers()
    auths = mapping_parser.get_auths()
    return (device_mappings, routemanagers, auths)


if __name__ == "__main__":
    # TODO: globally destroy all threads upon sys.exit() for example
    set_log_and_verbosity(log)
    install_thread_excepthook()

    webhook_helper = WebhookHelper(args)

    if args.db_method == "rm":
        db_wrapper = RmWrapper(args, webhook_helper)
    elif args.db_method == "monocle":
        db_wrapper = MonocleWrapper(args, webhook_helper)
    else:
        log.error("Invalid db_method in config. Exiting")
        sys.exit(1)
    webhook_helper.set_db_wrapper(db_wrapper)
    db_wrapper.create_hash_database_if_not_exists()
    db_wrapper.check_and_create_spawn_tables()
    db_wrapper.create_quest_database_if_not_exists()
    db_wrapper.create_status_database_if_not_exists()
    db_wrapper.create_usage_database_if_not_exists()
    version = MADVersion(args, db_wrapper)
    version.get_version()

    if args.clean_hash_database:
        log.info('Cleanup Hash Database and www_hash folder')
        db_wrapper.delete_hash_table('999', '')
        for file in glob.glob("ocr/www_hash/*.jpg"):
            os.remove(file)
        sys.exit(0)

    if not os.path.exists(args.raidscreen_path):
        log.info('Raidscreen directory created')
        os.makedirs(args.raidscreen_path)

    if not args.only_scan and not args.with_madmin and not args.only_ocr and not args.only_routes:
        log.error("No runmode selected. \nAllowed modes:\n"
                  " -wm    ---- start madmin (browserbased monitoring/configuration)\n"
                  " -os    ---- start scanner/devicecontroller\n"
                  " -oo    ---- start OCR analysis of screenshots\n"
                  " -or    ---- only calculate routes\nExiting")
        sys.exit(1)

    t_mitm = None
    mitm_receiver = None
    ws_server = None
    t_ws = None
    t_file_watcher = None
    if args.only_scan or args.only_routes:

        filename = os.path.join('configs', 'mappings.json')
        if not os.path.exists(filename):
            if not args.with_madmin:
                log.fatal("No mappings.json found - start madmin with with_madmin in config or copy example")
                sys.exit(1)

            log.fatal("No mappings.json found - starting setup mode with madmin.")
            log.fatal("Open Madmin (ServerIP with Port " + str(args.madmin_port) + ") - 'Mapping Editor' and restart.")
            generate_mappingjson()
        else:

            try:
                (device_mappings, routemanagers, auths) = load_mappings(db_wrapper)
            except KeyError as e:
                log.fatal("Could not parse mappings. Please check those. Description: %s" % str(e))
                sys.exit(1)
            except RuntimeError as e:
                log.fatal("There is something wrong with your mappings. Description: %s" % str(e))
                sys.exit(1)

            if args.only_routes:
                log.info("Done calculating routes!")
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
                    log.error('No-OCR Mode is activated - No OCR Mode possible.')
                    log.error('Check your config.ini and be sure that CV2 and Tesseract is installed')
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

            log.info('Starting scanner')
            ws_server = WebsocketServer(args, mitm_mapper, db_wrapper,
                                        routemanagers, device_mappings, auths, pogoWindowManager)
            t_ws = Thread(name='scanner', target=ws_server.start_server)
            t_ws.daemon = False
            t_ws.start()

            webhook_worker = None
            if args.webhook:
                from webhook.webhookworker import WebhookWorker

                webhook_worker = WebhookWorker(args, db_wrapper, routemanagers)
                t_whw = Thread(name="webhook_worker", target=webhook_worker.run_worker)
                t_whw.daemon = False
                t_whw.start()

            log.info("Starting file watcher for mappings.json changes.")
            t_file_watcher = Thread(name='file_watcher', target=file_watcher,
                                    args=(db_wrapper, mitm_mapper, ws_server, webhook_worker))
            t_file_watcher.daemon = False
            t_file_watcher.start()

    if args.only_ocr:
        from ocr.copyMons import MonRaidImages

        MonRaidImages.runAll(args.pogoasset, db_wrapper=db_wrapper)

        log.info('Starting OCR worker')
        t_observ = Thread(name='observer', target=start_ocr_observer, args=(args, db_wrapper,))
        t_observ.daemon = True
        t_observ.start()

    if args.with_madmin:
        log.info('Starting Madmin on Port: %s' % str(args.madmin_port))
        t_flask = Thread(name='madmin', target=start_madmin, args=(args, db_wrapper,))
        t_flask.daemon = True
        t_flask.start()

    if args.statistic:
        if args.only_ocr or args.only_scan:
            t_usage = Thread(name='system',
                             target=get_system_infos, args=(db_wrapper,))
            t_usage.daemon = False
            t_usage.start()
        else:
            log.warning("Dont collect system usage just for MADmin")

    log.info('Starting log cleanup worker')
    t_cleanup = Thread(name='cleanuplogs',
                       target=delete_old_logs, args=(args.cleanup_age,))
    t_cleanup.daemon = True
    t_cleanup.start()

    try:
        while True:
            time.sleep(10)
    finally:
        db_wrapper = None
        log.fatal("Stop called")
        terminate_mad.set()
        # now cleanup all threads...
        webhook_helper.stop_helper()
        # TODO: check against args or init variables to None...
        if t_mitm is not None and mitm_receiver is not None:
            mitm_receiver.stop_receiver()
        if ws_server is not None:
            ws_server.stop_server()
            t_ws.join()
        if t_file_watcher is not None:
            t_file_watcher.join()
        sys.exit(0)