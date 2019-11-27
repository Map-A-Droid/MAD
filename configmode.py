import os
import sys
from threading import Thread

from db.DbWrapper import DbWrapper
from db.DbFactory import DbFactory
from utils.MappingManager import MappingManagerManager, MappingManager
from utils.logging import initLogging, logger
from utils.version import MADVersion
from utils.walkerArgs import parseArgs
import utils.data_manager
from websocket.WebsocketServer import WebsocketServer
from utils.updater import deviceUpdater
from utils.functions import generate_mappingjson

args = parseArgs()
os.environ['LANGUAGE'] = args.language
initLogging(args)


def create_folder(folder):
    if not os.path.exists(folder):
        logger.info(str(folder) + ' created')
        os.makedirs(folder)


def start_madmin(args, db_wrapper: DbWrapper, ws_server, mapping_manager: MappingManager, data_manager, deviceUpdater, jobstatus):
    from madmin.madmin import madmin_start
    madmin_start(args, db_wrapper, ws_server, mapping_manager, data_manager, deviceUpdater, jobstatus)


if __name__ == "__main__":
    logger.info('Starting MAD config mode')
    filename = os.path.join('configs', 'config.ini')
    if not os.path.exists(filename):
        logger.error(
            'config.ini file not found. Check configs folder and copy example config')
        sys.exit(1)

    filename = args.mappings
    if not os.path.exists(filename):
        generate_mappingjson(args.mappings)

    create_folder(args.file_path)
    create_folder(args.upload_path)

    db_wrapper, db_pool_manager = DbFactory.get_wrapper(args)

    version = MADVersion(args, db_wrapper)
    version.get_version()

    data_manager = utils.data_manager.DataManager(logger, args)

    MappingManagerManager.register('MappingManager', MappingManager)
    mapping_manager_manager = MappingManagerManager()
    mapping_manager_manager.start()
    mapping_manager_stop_event = mapping_manager_manager.Event()
    mapping_manager: MappingManager = mapping_manager_manager.MappingManager(db_wrapper, args, data_manager, True)

    ws_server = WebsocketServer(args, None, db_wrapper, mapping_manager, None, True)
    t_ws = Thread(name='scanner', target=ws_server.start_server)
    t_ws.daemon = False
    t_ws.start()

    jobstatus: dict = {}

    device_Updater = deviceUpdater(ws_server, args, jobstatus)

    logger.success(
        'Starting MADmin on port {} - Open a browser, visit MADmin and go to "Settings"', int(args.madmin_port))
    t_flask = Thread(name='madmin', target=start_madmin,
                     args=(args, db_wrapper, ws_server, mapping_manager, data_manager, device_Updater, jobstatus))
    t_flask.daemon = False
    t_flask.start()
