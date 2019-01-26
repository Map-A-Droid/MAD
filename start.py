import datetime
import glob
import logging
import os
#os.environ['PYTHONASYNCIODEBUG'] = '1'
import sys
import time
from threading import Thread

from colorlog import ColoredFormatter
from watchdog.observers import Observer

from db.monocleWrapper import MonocleWrapper
from db.rmWrapper import RmWrapper
from mitm_receiver.MitmMapper import MitmMapper
from utils.mappingParser import MappingParser
from utils.walkerArgs import parseArgs
from utils.webhookHelper import WebhookHelper
from utils.madGlobals import MadGlobals
from websocket.WebsocketServerBase import WebsocketServerBase


class LogFilter(logging.Filter):

    def __init__(self, level):
        super().__init__()
        self.level = level

    def filter(self, record):
        return record.levelno < self.level


args = parseArgs()

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


def set_log_and_verbosity(log):
    # Always write to log file.
    args = parseArgs()
    # Create directory for log files.
    if not os.path.exists(args.log_path):
        os.mkdir(args.log_path)
    if not args.no_file_logs:
        filename = os.path.join(args.log_path, args.log_filename)
        filelog = logging.FileHandler(filename)
        filelog.setFormatter(logging.Formatter(
            '%(asctime)s [%(threadName)18s][%(module)14s][%(levelname)8s] ' +
            '%(message)s'))
        log.addHandler(filelog)

    if args.verbose:
        log.setLevel(logging.DEBUG)
    else:
        log.setLevel(logging.INFO)


def start_scan(mitm_mapper, db_wrapper, routemanagers, device_mappings, auths):
    wsRunning = WebsocketServerBase(args, args.ws_ip, int(args.ws_port), mitm_mapper, db_wrapper, routemanagers,
                                    device_mappings, auths)
    wsRunning.start_server()


def start_ocr_observer(args, db_helper):
    from ocr.fileObserver import checkScreenshot
    observer = Observer()
    log.error(args.raidscreen_path)
    observer.schedule(checkScreenshot(args, db_helper), path=args.raidscreen_path)
    observer.start()


def start_madmin():
    from madmin.madmin import app
    app.run(host=args.madmin_ip, port=int(args.madmin_port), threaded=True, use_reloader=False)


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


def sleeptimer():
    sleeptime = args.sleepinterval
    sts1 = sleeptime[0].split(':')
    sts2 = sleeptime[1].split(':')
    while True:
        tmFrom = datetime.datetime.now().replace(hour=int(sts1[0]),minute=int(sts1[1]),second=0,microsecond=0)
        tmTil = datetime.datetime.now().replace(hour=int(sts2[0]),minute=int(sts2[1]),second=0,microsecond=0)
        tmNow = datetime.datetime.now()

        # check if current time is past start time
        # and the day has changed already. thus shift
        # start time back to the day before
        if tmFrom > tmTil > tmNow:
            tmFrom = tmFrom + datetime.timedelta(days=-1)

        # check if start time is past end time thus
        # shift start time one day into the future
        if tmTil < tmFrom:
            tmTil = tmTil + datetime.timedelta(days=1)

        log.debug("Time now: %s" % tmNow)
        log.debug("Time From: %s" % tmFrom)
        log.debug("Time Til: %s" % tmTil)

        if tmFrom <= tmNow < tmTil:
            log.info('Going to sleep - bye bye')
            MadGlobals.sleep = True

            while MadGlobals.sleep:
                log.info("Currently sleeping...zzz")
                log.debug("Time now: %s" % tmNow)
                log.debug("Time From: %s" % tmFrom)
                log.debug("Time Til: %s" % tmTil)
                tmNow = datetime.datetime.now()
                log.info('Still sleeping, current time... %s' % str(tmNow.strftime("%H:%M")))
                if tmNow >= tmTil:
                    log.warning('sleeptimer: Wakeup - here we go ...')
                    MadGlobals.sleep = False
                    break
                time.sleep(30)
        time.sleep(30)


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
                log.fatal("No mappings.json found - start madmin with with_madmin in config or copy example")
                sys.exit(1)
                
            log.fatal("No mappings.json found - starting setup mode with madmin.")
            log.fatal("Open Madmin (ServerIP with Port " + str(args.madmin_port) + ") - 'Mapping Editor' and restart.")
            generate_mappingjson()
        else:

            try:
                mapping_parser = MappingParser(db_wrapper)
                device_mappings = mapping_parser.get_devicemappings()
                routemanagers = mapping_parser.get_routemanagers()
                auths = mapping_parser.get_auths()
            except KeyError as e:
                log.fatal("Could not parse mappings. Please check those. Description: %s" % str(e))
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
        t_observ = Thread(name='observer', target=start_ocr_observer, args=(args, db_wrapper,))
        t_observ.daemon = True
        t_observ.start()

    if args.with_madmin:
        log.info('Starting Madmin on Port: %s' % str(args.madmin_port))
        t_flask = Thread(name='madmin', target=start_madmin)
        t_flask.daemon = False
        t_flask.start()

    if args.sleeptimer:
        log.info('Starting Sleeptimer....')
        t_sleeptimer = Thread(name='sleeptimer',
                              target=sleeptimer)
        t_sleeptimer.daemon = True
        t_sleeptimer.start()

    while True:
        time.sleep(10)
