import logging
import os

from flask import Flask, render_template
from flask.logging import default_handler
from werkzeug.middleware.proxy_fix import ProxyFix

import mapadroid
from mapadroid.db.DbWrapper import DbWrapper
from mapadroid.mad_apk import AbstractAPKStorage
from mapadroid.madmin.api import APIEntry
from mapadroid.madmin.reverseproxy import ReverseProxied
from mapadroid.madmin.routes.apks import apk_manager
from mapadroid.madmin.routes.config import config
from mapadroid.madmin.routes.control import control
from mapadroid.madmin.routes.map import map
from mapadroid.madmin.routes.path import path
from mapadroid.madmin.routes.statistics import statistics
from mapadroid.madmin.routes.event import event
from mapadroid.utils import MappingManager
from mapadroid.utils.logging import InterceptHandler, logger


app = Flask(__name__,
            static_folder=os.path.join(mapadroid.MAD_ROOT, 'static/madmin/static'),
            template_folder=os.path.join(mapadroid.MAD_ROOT, 'static/madmin/templates'))
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

app.config['UPLOAD_FOLDER'] = 'temp'
app.config['MAX_CONTENT_LENGTH'] = 200 * 1024 * 1024
app.secret_key = "8bc96865945be733f3973ba21d3c5949"
log = logger


@app.errorhandler(500)
def internal_error(exception):
    logger.opt(exception=True).critical("An unhanded exception occurred!")
    return render_template('500.html'), 500


def madmin_start(args, db_wrapper: DbWrapper, ws_server, mapping_manager: MappingManager, data_manager,
                 deviceUpdater, jobstatus, storage_obj: AbstractAPKStorage):
    # load routes
    if args.madmin_base_path:
        app.wsgi_app = ReverseProxied(app.wsgi_app, script_name=args.madmin_base_path)

    statistics(db_wrapper, args, app, mapping_manager, data_manager)
    control(db_wrapper, args, mapping_manager, ws_server, logger, app, deviceUpdater)
    map(db_wrapper, args, mapping_manager, app, data_manager)
    APIEntry(logger, app, data_manager, mapping_manager, ws_server, args.config_mode, storage_obj)
    config(db_wrapper, args, logger, app, mapping_manager, data_manager)
    path(db_wrapper, args, app, mapping_manager, jobstatus, data_manager)
    apk_manager(db_wrapper, args, app, mapping_manager, jobstatus, storage_obj)
    event(db_wrapper, args, logger, app, mapping_manager, data_manager)

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
