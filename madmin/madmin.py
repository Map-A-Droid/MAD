import sys

from flask import (Flask)
from gevent.pywsgi import WSGIServer

from utils.logging import LogLevelChanger, logger
from utils.mappingParser import MappingParser

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


def madmin_start(arg_args, arg_db_wrapper, ws_server):
    # load mappings
    mapping_parser = MappingParser(arg_db_wrapper, arg_args)

    # load routes
    statistics(arg_db_wrapper, arg_args, app)
    control(arg_db_wrapper, arg_args, mapping_parser, ws_server, logger, app)
    map(arg_db_wrapper, arg_args, mapping_parser, app)
    config(arg_db_wrapper, arg_args, logger, app)
    ocr(arg_db_wrapper, arg_args, logger, app)
    path(arg_db_wrapper, arg_args, app)

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

