import datetime
import glob
import logging
import os
#os.environ['PYTHONASYNCIODEBUG'] = '1'
import sys
import time
from logging.handlers import RotatingFileHandler
from threading import Thread

from colorlog import ColoredFormatter
from db.monocleWrapper import MonocleWrapper
from db.rmWrapper import RmWrapper
from mitm_receiver.MitmMapper import MitmMapper
from utils.mappingParser import MappingParser
from utils.version import MADVersion
from utils.walkerArgs import parseArgs
from utils.webhookHelper import WebhookHelper
from watchdog.observers import Observer
from websocket.WebsocketServer import WebsocketServer


class LogFilter(logging.Filter):

    def __init__(self, level):
        super().__init__()
        self.level = level

    def filter(self, record):
        return record.levelno < self.level


args = parseArgs()
os.environ['LANGUAGE'] = args.language

console = logging.StreamHandler()
nextRaidQueue = []

if not args.verbose:
    console.setLevel(logging.INFO)

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

console.setFormatter(formatter)

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

log = logging.getLogger()

log.addHandler(stdout_hdlr)
log.addHandler(stderr_hdlr)


def handle_exception(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return

    log.error("Uncaught exception", exc_info=(
        exc_type, exc_value, exc_traceback))


sys.excepthook = handle_exception


def set_log_and_verbosity(log):
    # Always write to log file.
    args = parseArgs()
    # Create directory for log files.
    if not os.path.exists(args.log_path):
        os.mkdir(args.log_path)
    if not args.no_file_logs:

        filename = os.path.join(args.log_path, args.log_filename)
        if not args.log_rotation:
            filelog = logging.FileHandler(filename)
        else:
            filelog = RotatingFileHandler(filename, maxBytes=args.log_rotation_file_size,
                                          backupCount=args.log_rotation_backup_count)
        filelog.setFormatter(logging.Formatter(
            '%(asctime)s [%(threadName)18s][%(module)14s][%(levelname)8s] ' +
            '%(message)s'))
        log.addHandler(filelog)

    if args.verbose:
        log.setLevel(logging.DEBUG)
    else:
        log.setLevel(logging.INFO)


def start_scan(mitm_mapper, db_wrapper, routemanagers, device_mappings, auths):
    # wsRunning = WebsocketServerBase(args, args.ws_ip, int(args.ws_port), mitm_mapper, db_wrapper, routemanagers,
    #                                 device_mappings, auths)
    wsRunning = WebsocketServer(
        args, mitm_mapper, db_wrapper, routemanagers, device_mappings, auths)
    wsRunning.start_server()


def start_ocr_observer(args, db_helper):
    from ocr.fileObserver import checkScreenshot
    observer = Observer()
    log.error(args.raidscreen_path)
    observer.schedule(checkScreenshot(args, db_helper),
                      path=args.raidscreen_path)
    observer.start()


def delete_old_logs(minutes):
    if minutes == "0":
        log.info('delete_old_logs: Search/Delete logs is disabled')
        return

    while True:
        log.info('delete_old_logs: Search/Delete logs older than ' +
                 str(minutes) + ' minutes')

        now = time.time()
        only_files = []

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


def start_madmin():
    from madmin.madmin import app
    app.run(host=args.madmin_ip, port=int(args.madmin_port),
            threaded=True, use_reloader=False)


# TODO: IP and port for receiver from args...
def start_mitm_receiver(mitm_mapper, auths, db_wrapper):
    from mitm_receiver.MITMReceiver import MITMReceiver
    mitm_receiver = MITMReceiver(args.mitmreceiver_ip, int(args.mitmreceiver_port),
                                 mitm_mapper, args, auths, db_wrapper)
    mitm_receiver.run_receiver()


def generate_mappingjson():
    import json
    newfile = {}
    newfile['areas'] = []
    newfile['auth'] = []
    newfile['devices'] = []
    with open('configs/mappings.json', 'w') as outfile:
        json.dump(newfile, outfile, indent=4, sort_keys=True)


if __name__ == "__main__":
    # TODO: globally destroy all threads upon sys.exit() for example
    set_log_and_verbosity(log)
    webhook_helper = WebhookHelper(args)

    if args.db_method == "rm":
        db_wrapper = RmWrapper(args, webhook_helper)
    elif args.db_method == "monocle":
        db_wrapper = MonocleWrapper(args, webhook_helper)
    else:
        log.error("Invalid db_method in config. Exiting")
        sys.exit(1)
    db_wrapper.create_hash_database_if_not_exists()
    db_wrapper.check_and_create_spawn_tables()
    db_wrapper.create_quest_database_if_not_exists()
    webhook_helper.set_gyminfo(db_wrapper)
    version = MADVersion(args, db_wrapper)
    version.get_version()

    if not db_wrapper.ensure_last_updated_column():
        log.fatal("Missing raids.last_updated column and couldn't create it")
        sys.exit(1)

    if args.clean_hash_database:
        log.info('Cleanup Hash Database and www_hash folder')
        db_wrapper.delete_hash_table('999', '')
        for file in glob.glob("ocr/www_hash/*.jpg"):
            os.remove(file)
        sys.exit(0)

    if not os.path.exists(args.raidscreen_path):
        log.info('Raidscreen directory created')
        os.makedirs(args.raidscreen_path)

    if not args.only_scan and not args.with_madmin and not args.only_ocr:
        log.error("No runmode selected. \nAllowed modes: "
                  " -wm    ---- start madmin (browserbased monitoring/configuration) "
                  " -os    ---- start scanner/devicecontroller "
                  "-oo     ---- start OCR analysis of screenshots\nExiting")
        sys.exit(1)

    if args.only_scan:

        filename = os.path.join('configs', 'mappings.json')
        if not os.path.exists(filename):
            if not args.with_madmin:
                log.fatal(
                    "No mappings.json found - start madmin with with_madmin in config or copy example")
                sys.exit(1)

            log.fatal("No mappings.json found - starting setup mode with madmin.")
            log.fatal("Open Madmin (ServerIP with Port " +
                      str(args.madmin_port) + ") - 'Mapping Editor' and restart.")
            generate_mappingjson()
        else:

            try:
                mapping_parser = MappingParser(db_wrapper)
                device_mappings = mapping_parser.get_devicemappings()
                routemanagers = mapping_parser.get_routemanagers()
                auths = mapping_parser.get_auths()
            except KeyError as e:
                log.fatal(
                    "Could not parse mappings. Please check those. Description: %s" % str(e))
                sys.exit(1)

            mitm_mapper = MitmMapper(device_mappings)
            ocr_enabled = False
            for routemanager in routemanagers.keys():
                area = routemanagers.get(routemanager, None)
                if area is None:
                    continue
                if "ocr" in area.get("mode", ""):
                    ocr_enabled = True
            if ocr_enabled:
                from ocr.copyMons import MonRaidImages
                MonRaidImages.runAll(args.pogoasset, db_wrapper=db_wrapper)

            t_flask = Thread(name='mitm_receiver', target=start_mitm_receiver,
                             args=(mitm_mapper, auths, db_wrapper))
            t_flask.daemon = False
            t_flask.start()

            log.info('Starting scanner....')
            t = Thread(target=start_scan, name='scanner', args=(mitm_mapper, db_wrapper, routemanagers,
                                                                device_mappings, auths,))
            t.daemon = True
            t.start()

    if args.only_ocr:
        from ocr.copyMons import MonRaidImages

        MonRaidImages.runAll(args.pogoasset, db_wrapper=db_wrapper)

        log.info('Starting OCR Thread....')
        t_observ = Thread(
            name='observer', target=start_ocr_observer, args=(args, db_wrapper,))
        t_observ.daemon = True
        t_observ.start()

    if args.with_madmin:
        log.info('Starting Madmin on Port: %s' % str(args.madmin_port))
        t_flask = Thread(name='madmin', target=start_madmin)
        t_flask.daemon = False
        t_flask.start()

    log.info('Starting Log Cleanup Thread....')
    t_cleanup = Thread(name='cleanuplogs',
                       target=delete_old_logs(args.cleanup_age))
    t_cleanup.join()
    t_cleanup.daemon = True
    t_cleanup.start()

    while True:
        time.sleep(10)
