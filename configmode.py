import os
import sys

from threading import Thread
from loguru import logger

from utils.walkerArgs import parseArgs
from db.monocleWrapper import MonocleWrapper
from db.rmWrapper import RmWrapper
from utils.version import MADVersion
from utils.logging import initLogging

args = parseArgs()
os.environ['LANGUAGE'] = args.language
initLogging(args)


def generate_mappingjson():
    import json
    newfile = {}
    newfile['areas'] = []
    newfile['auth'] = []
    newfile['devices'] = []
    newfile['walker'] = []
    with open('configs/mappings.json', 'w') as outfile:
        json.dump(newfile, outfile, indent=4, sort_keys=True)


def start_madmin(args, db_wrapper):
    from madmin.madmin import madmin_start
    madmin_start(args, db_wrapper)


if __name__ == "__main__":
    filename = os.path.join('configs', 'config.ini')
    if not os.path.exists(filename):
        logger.error('Config.ini not found - check configs folder and copy .example')
        sys.exit(1)

    filename = os.path.join('configs', 'mappings.json')
    if not os.path.exists(filename):
        generate_mappingjson()

    if args.db_method == "rm":
        db_wrapper = RmWrapper(args)
    elif args.db_method == "monocle":
        db_wrapper = MonocleWrapper(args)
    else:
        logger.error("Invalid db_method in config. Exiting")
        sys.exit(1)

    version = MADVersion(args, db_wrapper)
    version.get_version()

    logger.success('Starting MADmin on port {} - open browser and click "Mapping Editor"', int(args.madmin_port))
    t_flask = Thread(name='madmin', target=start_madmin, args=(args, db_wrapper))
    t_flask.daemon = False
    t_flask.start()
