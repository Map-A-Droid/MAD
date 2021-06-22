import logging
import os
from typing import Dict, List

import aiohttp_jinja2
import jinja2
from aiohttp import web
from aiohttp.web_runner import TCPSite, UnixSite

import mapadroid
from mapadroid.db.DbWrapper import DbWrapper
from mapadroid.db.helper.SettingsDeviceHelper import SettingsDeviceHelper
from mapadroid.db.model import SettingsDevice
from mapadroid.madmin.endpoints.api.apks import register_api_apk_endpoints
from mapadroid.madmin.endpoints.api.autoconf import register_api_autoconf_endpoints
from mapadroid.madmin.endpoints.api.resources import register_api_resources_endpoints
from mapadroid.madmin.endpoints.routes import register_routes_root_endpoints
from mapadroid.madmin.endpoints.routes.apk import register_routes_apk_endpoints
from mapadroid.madmin.endpoints.routes.autoconfig import register_routes_autoconfig_endpoints
from mapadroid.madmin.endpoints.routes.control import register_routes_control_endpoints
from mapadroid.madmin.endpoints.routes.event import register_routes_event_endpoints
from mapadroid.madmin.endpoints.routes.map import register_routes_map_endpoints
from mapadroid.madmin.endpoints.routes.misc import register_routes_misc_endpoints
from mapadroid.madmin.endpoints.routes.settings import register_routes_settings_endpoints
from mapadroid.madmin.endpoints.routes.statistics import register_routes_statistics_endpoints
from mapadroid.mapping_manager import MappingManager
from mapadroid.utils.JinjaFilters import base64Filter, mad_json_filter
from mapadroid.utils.logging import InterceptHandler, LoggerEnums, get_logger
from mapadroid.utils.updater import DeviceUpdater
from mapadroid.websocket.WebsocketServer import WebsocketServer

logger = get_logger(LoggerEnums.madmin)


class MADmin(object):
    def __init__(self, args, db_wrapper: DbWrapper, ws_server: WebsocketServer, mapping_manager: MappingManager,
                 device_updater: DeviceUpdater, jobstatus, storage_obj):
        #app.add_template_global(name='app_config_mode', f=args.config_mode)
        # Determine if there are duplicate MACs

        self._db_wrapper: DbWrapper = db_wrapper
        self._args = args
        self._app = None
        self._mapping_manager: MappingManager = mapping_manager
        self._storage_obj = storage_obj
        self._device_updater: DeviceUpdater = device_updater
        self._ws_server: WebsocketServer = ws_server
        self._jobstatus = jobstatus
        self._plugin_hotlink: list = []

    @logger.catch()
    async def madmin_start(self) -> web.AppRunner:
        self._app = web.Application()

        static_folder_path = os.path.join(mapadroid.MAD_ROOT, 'static/madmin/static')
        template_folder_path = os.path.join(mapadroid.MAD_ROOT, 'static/madmin/templates')
        self._app.router.add_static("/static", static_folder_path, append_version=True)
        self._app['static_root_url'] = '/static'
        self._app['UPLOAD_FOLDER'] = 'temp'
        self._app['MAX_CONTENT_LENGTH'] = 200 * 1024 * 1024
        self._app.secret_key = "8bc96865945be733f3973ba21d3c5949"
        self._app['SEND_FILE_MAX_AGE_DEFAULT'] = 0
        self._app['db_wrapper'] = self._db_wrapper
        self._app['mad_args'] = self._args
        self._app['mapping_manager'] = self._mapping_manager
        self._app['websocket_server'] = self._ws_server
        self._app["plugin_hotlink"] = None # TODO
        self._app["storage_obj"] = self._storage_obj
        self._app['device_updater'] = self._device_updater

        jinja2_env = aiohttp_jinja2.setup(self._app, loader=jinja2.FileSystemLoader(template_folder_path))
        jinja2_env.filters["base64"] = base64Filter
        jinja2_env.filters["madJson"] = mad_json_filter
        register_routes_root_endpoints(self._app)
        register_api_apk_endpoints(self._app)
        register_api_autoconf_endpoints(self._app)
        register_api_resources_endpoints(self._app)

        # TODO: fix storage obj...
        register_routes_apk_endpoints(self._app)
        register_routes_autoconfig_endpoints(self._app)
        register_routes_control_endpoints(self._app)
        register_routes_settings_endpoints(self._app)
        register_routes_misc_endpoints(self._app)
        register_routes_map_endpoints(self._app)
        register_routes_event_endpoints(self._app)
        register_routes_statistics_endpoints(self._app)
        try:
            async with self._db_wrapper as session, session:
                duplicate_macs: Dict[str, List[SettingsDevice]] = await SettingsDeviceHelper.get_duplicate_mac_entries(
                    session)
                if len(duplicate_macs) > 0:
                    pass
                # TODO
                    # self._app.add_template_global(name='app_dupe_macs_devs', f=duplicate_macs)
                # self._app.add_template_global(name='app_dupe_macs', f=bool(len(duplicate_macs) > 0))
        except Exception as e:  # noqa: E722 B001
            logger.exception(e)
            logger.opt(exception=True).critical('Unable to load MADmin component')

        # TODO: Logger for madmin
        log = logging.getLogger('werkzeug')
        handler = InterceptHandler(log_section=LoggerEnums.madmin)
        log.addHandler(handler)

        runner: web.AppRunner = web.AppRunner(self._app)
        await runner.setup()
        if self._args.madmin_unix_socket:
            site: UnixSite = web.UnixSite(runner, self._args.madmin_unix_socket)
            logger.info("Madmin starting at {}", self._args.madmin_unix_socket)
        else:
            site: TCPSite = web.TCPSite(runner, "127.0.0.1", 5000)
            logger.info('Madmin starting at http://127.0.0.1:5000')
        await site.start()
        # TODO: Return runner and call     await runner.cleanup()
        logger.info('Finished madmin')
        return runner

    def add_route(self, routes):
        for route, view_func in routes:
            self._app.route(route, methods=['GET', 'POST'])(view_func)

    def register_plugin(self, pluginname):
        self._app.register_blueprint(pluginname)

    def add_plugin_hotlink(self, name, link, plugin, description, author, url, linkdescription, version):
        self._plugin_hotlink.append({"Plugin": plugin, "linkname": name, "linkurl": link,
                                     "description": description, "author": author, "authorurl": url,
                                     "linkdescription": linkdescription, 'version': version})
