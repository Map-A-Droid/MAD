import os
import sys
from threading import Thread

from db.dbWrapperBase import DbWrapperBase
from db.DbFactory import DbFactory
from utils.MappingManager import MappingManagerManager, MappingManager
from utils.logging import initLogging, logger
from utils.version import MADVersion
from utils.walkerArgs import parseArgs
from websocket.WebsocketServer import WebsocketServer
from utils.updater import deviceUpdater

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
    with open(args.mappings, 'w') as outfile:
        json.dump(newfile, outfile, indent=4, sort_keys=True)


def create_folder(folder):
    if not os.path.exists(folder):
        logger.info(str(folder) + ' created')
        os.makedirs(folder)


def start_madmin(args, db_wrapper: DbWrapperBase, ws_server, mapping_manager: MappingManager, deviceUpdater, jobstatus):
    from madmin.madmin import madmin_start
    madmin_start(args, db_wrapper, ws_server, mapping_manager, deviceUpdater, jobstatus)


if __name__ == "__main__":
    logger.info('Start MAD configmode - pls wait')
    filename = os.path.join('configs', 'config.ini')
    if not os.path.exists(filename):
        logger.error(
            'config.ini file not found - check configs folder and copy .example')
        sys.exit(1)

    filename = args.mappings
    if not os.path.exists(filename):
        generate_mappingjson()

    create_folder(args.file_path)
    create_folder(args.upload_path)

    db_wrapper, db_wrapper_manager = DbFactory.get_wrapper(args)

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
    mapping_manager: MappingManager = mapping_manager_manager.MappingManager(db_wrapper, args, True)

    ws_server = WebsocketServer(args, None, db_wrapper, mapping_manager, None, True)
    t_ws = Thread(name='scanner', target=ws_server.start_server)
    t_ws.daemon = False
    t_ws.start()

    jobstatus: dict = {}

    device_Updater = deviceUpdater(ws_server, args, jobstatus)

    logger.success(
        'Starting MADmin on port {} - open browser and click "Mapping Editor"', int(args.madmin_port))
    t_flask = Thread(name='madmin', target=start_madmin,
                     args=(args, db_wrapper, ws_server, mapping_manager, device_Updater, jobstatus))
    t_flask.daemon = False
    t_flask.start()
