import sys

import logging
from flask import Flask
from flask.logging import default_handler
from werkzeug.utils import secure_filename

from db.dbWrapperBase import DbWrapperBase
from utils.MappingManager import MappingManager
from utils.logging import InterceptHandler, logger
# routes
from madmin.routes.statistics import statistics
from madmin.routes.control import control
from madmin.routes.map import map
from madmin.routes.config import config
from madmin.routes.path import path

sys.path.append("..")  # Adds higher directory to python modules path.

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'temp'
app.config['MAX_CONTENT_LENGTH'] = 200 * 1024 * 1024
app.secret_key = "8bc96865945be733f3973ba21d3c5949"
log = logger


def madmin_start(args, db_wrapper: DbWrapperBase, ws_server, mapping_manager: MappingManager, deviceUpdater,
                 jobstatus):
    # load routes

    statistics(db_wrapper, args, app, mapping_manager)
    control(db_wrapper, args, mapping_manager, ws_server, logger, app, deviceUpdater)
    map(db_wrapper, args, mapping_manager, app)
    config(db_wrapper, args, logger, app, mapping_manager)
    path(db_wrapper, args, app, mapping_manager, jobstatus)

    app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0
    app.logger.removeHandler(default_handler)
    logging.basicConfig(handlers=[InterceptHandler()], level=0)
    app.run(host=args.madmin_ip, port=int(args.madmin_port), threaded=True)


@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers',
                         'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods',
                         'GET,PUT,POST,DELETE,OPTIONS')
    return response
