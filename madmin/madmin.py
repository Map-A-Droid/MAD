import sys

from flask import (Flask)
from gevent.pywsgi import WSGIServer

from db.dbWrapperBase import DbWrapperBase
from utils.MappingManager import MappingManager
from utils.logging import LogLevelChanger, logger

# routes
from madmin.routes.statistics import statistics
from madmin.routes.control import control
from madmin.routes.map import map
from madmin.routes.config import config
from madmin.routes.ocr import ocr
from madmin.routes.path import path

sys.path.append("..")  # Adds higher directory to python modules path.

app = Flask(__name__)
log = logger


def madmin_start(arg_args, db_wrapper: DbWrapperBase, ws_server, mapping_manager: MappingManager):
    # load routes
    statistics(db_wrapper, arg_args, app)
    control(db_wrapper, arg_args, mapping_manager, ws_server, logger, app)
    map(db_wrapper, arg_args, mapping_manager, app)
    config(db_wrapper, arg_args, logger, app)
    ocr(db_wrapper, arg_args, logger, app)
    path(db_wrapper, arg_args, app)

    httpsrv = WSGIServer((arg_args.madmin_ip, int(
        arg_args.madmin_port)), app.wsgi_app, log=LogLevelChanger)
    httpsrv.serve_forever()


@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers',
                         'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods',
                         'GET,PUT,POST,DELETE,OPTIONS')
    return response

