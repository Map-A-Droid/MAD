import os
import sys

from utils.walkerArgs import parseArgs
from threading import Thread
from db.monocleWrapper import MonocleWrapper
from db.rmWrapper import RmWrapper
from utils.version import MADVersion

args = parseArgs()
os.environ['LANGUAGE']=args.language

def generate_mappingjson():
    import json
    newfile = {}
    newfile['areas'] = []
    newfile['auth'] = []
    newfile['devices'] = []
    with open('configs/mappings.json', 'w') as outfile:
        json.dump(newfile, outfile, indent=4, sort_keys=True)

def start_madmin(args, db_wrapper):
    from madmin.madmin import madmin_start
    madmin_start(args, db_wrapper)
    
if __name__ == "__main__":
    filename = os.path.join('configs', 'config.ini')
    if not os.path.exists(filename):
        print('Config.ini not found - check configs folder and copy .example')
        sys.exit(1)
    
    filename = os.path.join('configs', 'mappings.json')
    if not os.path.exists(filename):
        generate_mappingjson()

    webhook_helper = None

    if args.db_method == "rm":
        db_wrapper = RmWrapper(args, webhook_helper)
    elif args.db_method == "monocle":
        db_wrapper = MonocleWrapper(args, webhook_helper)
    else:
        log.error("Invalid db_method in config. Exiting")
        sys.exit(1)

    version = MADVersion(args, db_wrapper)
    version.get_version()
    
    print('Starting MADmin with Port {} - open browser  and click "Mapping Editor"'.format(int(args.madmin_port)))
    t_flask = Thread(name='madmin', target=start_madmin, args=(args, db_wrapper))
    t_flask.daemon = False
    t_flask.start()