import sys

import logging
from flask import Flask
from flask.logging import default_handler

from db.dbWrapperBase import DbWrapperBase
from utils.MappingManager import MappingManager
from utils.logging import InterceptHandler, logger
from utils.local_api import LocalAPI

# routes
from madmin.routes.statistics import statistics
from madmin.routes.control import control
from madmin.routes.map import map
from madmin.routes.config import config
from madmin.routes.ocr import ocr
from madmin.routes.path import path
from madmin.api import APIHandler


sys.path.append("..")  # Adds higher directory to python modules path.

app = Flask(__name__)
log = logger


def madmin_start(args, db_wrapper: DbWrapperBase, ws_server, mapping_manager: MappingManager):
    app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0
    app.config["basePath"] = args.madmin_base_path
    app.logger.removeHandler(default_handler)
    logging.basicConfig(handlers=[InterceptHandler()], level=0)

    # load routes
    statistics(db_wrapper, args, app)
    control(db_wrapper, args, mapping_manager, ws_server, logger, app)
    map(db_wrapper, args, mapping_manager, app)
    api = APIHandler(logger, args, app)
    config(db_wrapper, args, logger, app, mapping_manager, api)
    ocr(db_wrapper, args, logger, app)
    path(db_wrapper, args, app)

    app.run(host=args.madmin_ip, port=int(args.madmin_port), threaded=True)


@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers',
                         'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods',
                         'GET,PUT,POST,DELETE,OPTIONS')
    return response
