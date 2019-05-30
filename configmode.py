import os
import sys
from threading import Thread

from db.dbWrapperBase import DbWrapperBase
from db.monocleWrapper import MonocleWrapper
from db.rmWrapper import RmWrapper
from utils.MappingManager import MappingManagerManager, MappingManager
from utils.logging import initLogging, logger
from utils.version import MADVersion
from utils.walkerArgs import parseArgs
from websocket.WebsocketServer import WebsocketServer

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
    newfile['devicesettings'] = []
    with open('configs/mappings.json', 'w') as outfile:
        json.dump(newfile, outfile, indent=4, sort_keys=True)


def start_madmin(args, db_wrapper: DbWrapperBase, ws_server, mapping_manager: MappingManager):
    from madmin.madmin import madmin_start
    madmin_start(args, db_wrapper, ws_server, mapping_manager)


if __name__ == "__main__":
    logger.info('Start MAD configmode - pls wait')
    filename = os.path.join('configs', 'config.ini')
    if not os.path.exists(filename):
        logger.error(
            'Config.ini not found - check configs folder and copy .example')
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

    db_wrapper.create_hash_database_if_not_exists()
    db_wrapper.check_and_create_spawn_tables()
    db_wrapper.create_quest_database_if_not_exists()
    db_wrapper.create_status_database_if_not_exists()
    db_wrapper.create_usage_database_if_not_exists()
    db_wrapper.create_statistics_databases_if_not_exists()
    version = MADVersion(args, db_wrapper)
    version.get_version()

    MappingManagerManager.register('MappingManager', MappingManager)
    mapping_manager_manager = MappingManagerManager()
    mapping_manager_manager.start()
    mapping_manager_stop_event = mapping_manager_manager.Event()
    mapping_manager: MappingManager = mapping_manager_manager.MappingManager(db_wrapper, args,
                                                                             mapping_manager_stop_event, False)

    ws_server = WebsocketServer(args, None, db_wrapper, mapping_manager, None, True)
    t_ws = Thread(name='scanner', target=ws_server.start_server)
    t_ws.daemon = False
    t_ws.start()

    logger.success(
        'Starting MADmin on port {} - open browser and click "Mapping Editor"', int(args.madmin_port))
    t_flask = Thread(name='madmin', target=start_madmin,
                     args=(args, db_wrapper, ws_server, mapping_manager,))
    t_flask.daemon = False
    t_flask.start()
