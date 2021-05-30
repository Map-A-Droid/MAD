import logging
import os
from typing import Dict, List

from flask import Flask, render_template
from werkzeug.middleware.proxy_fix import ProxyFix

import mapadroid
from mapadroid.db.DbWrapper import DbWrapper
from mapadroid.db.helper.SettingsDeviceHelper import SettingsDeviceHelper
from mapadroid.db.model import SettingsDevice
from mapadroid.madmin.api import APIEntry
from mapadroid.madmin.reverseproxy import ReverseProxied
from mapadroid.madmin.routes.apks import APKManager
from mapadroid.madmin.routes.autoconf import AutoConfigManager
from mapadroid.madmin.routes.config import MADminConfig
from mapadroid.madmin.routes.control import MADminControl
from mapadroid.madmin.routes.event import MADminEvent
from mapadroid.madmin.routes.map import MADminMap
from mapadroid.madmin.routes.path import MADminPath
from mapadroid.madmin.routes.statistics import MADminStatistics
from mapadroid.mapping_manager import MappingManager
from mapadroid.utils.logging import InterceptHandler, LoggerEnums, get_logger
from mapadroid.utils.updater import DeviceUpdater
from mapadroid.websocket.WebsocketServer import WebsocketServer

logger = get_logger(LoggerEnums.madmin)
app = Flask(__name__,
            static_folder=os.path.join(mapadroid.MAD_ROOT, 'static/madmin/static'),
            template_folder=os.path.join(mapadroid.MAD_ROOT, 'static/madmin/templates'))
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)
app.config['UPLOAD_FOLDER'] = 'temp'
app.config['MAX_CONTENT_LENGTH'] = 200 * 1024 * 1024
app.secret_key = "8bc96865945be733f3973ba21d3c5949"
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0
log = logging.getLogger('werkzeug')
handler = InterceptHandler(log_section=LoggerEnums.madmin)
log.addHandler(handler)


@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers',
                         'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods',
                         'GET,PUT,POST,DELETE,OPTIONS')
    return response


@app.errorhandler(500)
def internal_error(self, exception):
    logger.opt(exception=True).critical("An unhandled exception occurred!")
    return render_template('500.html'), 500


class MADmin(object):
    def __init__(self, args, db_wrapper: DbWrapper, ws_server: WebsocketServer, mapping_manager: MappingManager,
                 device_updater: DeviceUpdater, jobstatus, storage_obj):
        app.add_template_global(name='app_config_mode', f=args.config_mode)
        # Determine if there are duplicate MACs

        self._db_wrapper: DbWrapper = db_wrapper
        self._args = args
        self._app = app
        self._mapping_manager: MappingManager = mapping_manager
        self._storage_obj = storage_obj
        self._device_updater: DeviceUpdater = device_updater
        self._ws_server: WebsocketServer = ws_server
        self._jobstatus = jobstatus
        self._plugin_hotlink: list = []
        self.path = MADminPath(self._db_wrapper, self._args, self._app, self._mapping_manager, self._jobstatus,
                               self._plugin_hotlink)
        self.map = MADminMap(self._db_wrapper, self._args, self._mapping_manager, self._app)
        self.statistics = MADminStatistics(self._db_wrapper, self._args, app, self._mapping_manager)
        self.control = MADminControl(self._db_wrapper, self._args, self._mapping_manager, self._ws_server, logger,
                                     self._app, self._device_updater)
        self.APIEntry = APIEntry(logger, self._app, self._db_wrapper, self._mapping_manager, self._ws_server,
                                 self._args.config_mode, self._storage_obj, self._args)
        self.config = MADminConfig(self._db_wrapper, self._args, logger, self._app, self._mapping_manager)
        self.apk_manager = APKManager(self._db_wrapper, self._args, self._app, self._mapping_manager, self._jobstatus,
                                      self._storage_obj)
        self.event = MADminEvent(self._db_wrapper, self._args, logger, self._app, self._mapping_manager)
        self.autoconf = AutoConfigManager(self._app, self._db_wrapper, self._args, self._storage_obj)

    @logger.catch()
    async def madmin_start(self):
        try:
            async with self._db_wrapper as session, session:
                duplicate_macs: Dict[str, List[SettingsDevice]] = await SettingsDeviceHelper.get_duplicate_mac_entries(
                    session)
                if len(duplicate_macs) > 0:
                    app.add_template_global(name='app_dupe_macs_devs', f=duplicate_macs)
                app.add_template_global(name='app_dupe_macs', f=bool(len(duplicate_macs) > 0))
            # load routes
            if self._args.madmin_base_path:
                self._app.wsgi_app = ReverseProxied(self._app.wsgi_app, script_name=self._args.madmin_base_path)
            # start modules
            self.path.start_modul()
            self.map.start_modul()
            self.statistics.start_modul()
            self.config.start_modul()
            self.apk_manager.start_modul()
            self.event.start_modul()
            self.control.start_modul()
            self.autoconf.start_modul()
            self._app.run(host=self._args.madmin_ip, port=int(self._args.madmin_port), threaded=True)
        except:  # noqa: E722 B001
            logger.opt(exception=True).critical('Unable to load MADmin component')
        logger.info('Finished madmin')

    def add_route(self, routes):
        for route, view_func in routes:
            self._app.route(route, methods=['GET', 'POST'])(view_func)

    def register_plugin(self, pluginname):
        self._app.register_blueprint(pluginname)

    def add_plugin_hotlink(self, name, link, plugin, description, author, url, linkdescription, version):
        self._plugin_hotlink.append({"Plugin": plugin, "linkname": name, "linkurl": link,
                                     "description": description, "author": author, "authorurl": url,
                                     "linkdescription": linkdescription, 'version': version})
