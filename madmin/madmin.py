import sys

import logging
from flask import Flask
from flask.logging import default_handler
from werkzeug.utils import secure_filename
from werkzeug.middleware.proxy_fix import ProxyFix

from db.DbWrapper import DbWrapper
from utils.MappingManager import MappingManager
from utils.logging import InterceptHandler, logger
# routes
from madmin.routes.statistics import statistics
from madmin.routes.control import control
from madmin.routes.map import map
from madmin.routes.config import config
from madmin.routes.path import path
from madmin.api import APIHandler
from madmin.reverseproxy import ReverseProxied


sys.path.append("..")  # Adds higher directory to python modules path.

app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1) 
app.config['UPLOAD_FOLDER'] = 'temp'
app.config['MAX_CONTENT_LENGTH'] = 200 * 1024 * 1024
app.secret_key = "8bc96865945be733f3973ba21d3c5949"
log = logger


def madmin_start(args, db_wrapper: DbWrapper, ws_server, mapping_manager: MappingManager, data_manager, deviceUpdater, jobstatus):
    # load routes
    if args.madmin_base_path:
        app.wsgi_app = ReverseProxied(app.wsgi_app, script_name=args.madmin_base_path)

    statistics(db_wrapper, args, app, mapping_manager)
    control(db_wrapper, args, mapping_manager, ws_server, logger, app, deviceUpdater)
    map(db_wrapper, args, mapping_manager, app)
    APIHandler(logger, args, app, data_manager)
    config(db_wrapper, args, logger, app, mapping_manager, data_manager)
    path(db_wrapper, args, app, mapping_manager, jobstatus)

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
