import configparser
import inspect
import os
import pkgutil
from abc import ABC, abstractmethod
from copy import copy
from typing import Dict

from aiohttp import web
import aiohttp_jinja2
import jinja2
from mapadroid.plugins.endpoints import register_plugin_endpoints


class Plugin(ABC):
    """Base class that each plugin must inherit from. within this class
    you must define the methods that all of your plugins must implement
    """

    def __init__(self, subapp_to_register_to: web.Application, mad_parts: Dict):
        self._subapp: web.Application = subapp_to_register_to
        self._mad_parts: Dict = mad_parts
        self._pluginconfig = configparser.ConfigParser()
        self._versionconfig = configparser.ConfigParser()
        self._rootdir = self._file_path()
        self._pluginconfig.read(self._rootdir + "/plugin.ini")
        self._versionconfig.read(self._rootdir + "/version.mpl")

        self.staticpath = self._rootdir + "/static/"
        self.templatepath = self._rootdir + "/template/"
        self.author = self._versionconfig.get("plugin", "author", fallback="unknown")
        self.url = self._versionconfig.get("plugin", "url", fallback="https://www.maddev.eu")
        self.description = self._versionconfig.get("plugin", "description", fallback="unknown")
        self.version = self._versionconfig.get("plugin", "version", fallback="unknown")
        self.pluginname = self._versionconfig.get("plugin", "pluginname", fallback="https://www.maddev.eu")

        # Modify the template and static loader of jinja2 to also consider the directories of the plugin
        env = aiohttp_jinja2.get_env(self._mad_parts["madmin"].get_app())
        paths = copy(env.loader.searchpath)
        paths.append(self.templatepath)
        env.loader = jinja2.FileSystemLoader(paths)
        self._subapp.router.add_static("/static", self.staticpath, append_version=True)

    async def run(self):
        if not self._pluginconfig.getboolean("plugin", "active", fallback=False):
            return False
        else:
            return await self._perform_operation()

    @abstractmethod
    async def _perform_operation(self) -> bool:
        """The method that we expect all plugins to implement. This is the
        method that our framework will call
        """
        pass

    @abstractmethod
    def _file_path(self) -> str:
        """
        Returns: Path to root of the custom plugin's directory

        """
        pass


class PluginCollection(object):
    """Upon creation, this class will read the plugins package for modules
    that contain a class definition that is inheriting from the Plugin class
    """

    def __init__(self, plugin_package, mad_parts):
        """Constructor that initiates the reading of all available plugins
        when an instance of the PluginCollection object is created
        """
        self.plugins = []
        self.seen_paths = []

        self.plugin_package = plugin_package
        self._mad_parts = mad_parts
        self._logger = self._mad_parts['logger']
        self._plugin_subapp = web.Application()
        self._plugin_subapp["plugin_package"] = plugin_package
        self._plugin_subapp["plugins"] = self.plugins
        self._plugin_subapp['db_wrapper'] = self._mad_parts["db_wrapper"]
        self._plugin_subapp['mad_args'] = self._mad_parts["args"]
        self._plugin_subapp['mapping_manager'] = self._mad_parts["mapping_manager"]
        self._plugin_subapp['websocket_server'] = self._mad_parts["ws_server"]
        self._plugin_subapp["plugin_hotlink"] = self._mad_parts['madmin'].get_plugin_hotlink()
        self._plugin_subapp["storage_obj"] = self._mad_parts["storage_elem"]
        self._plugin_subapp['device_updater'] = self._mad_parts["device_Updater"]
        register_plugin_endpoints(self._plugin_subapp)

        self.__load_plugins()

    async def finish_init(self):
        await self.__apply_all_plugins_on_value()
        self.__register_to_madmin()

    def __register_to_madmin(self):
        self._mad_parts['madmin'].register_plugin("custom_plugins", self._plugin_subapp)

    def __load_plugins(self):
        """Reset the list of all plugins and initiate the walk over the main
        provided plugin package to load all available plugins
        """
        self.plugins = []
        self.seen_paths = []

        self._logger.info(f'Looking for plugins under package {self.plugin_package}')
        self.__walk_package(self.plugin_package)

    async def __apply_all_plugins_on_value(self):
        """Apply all of the plugins on the argument supplied to this function
        """
        for plugin in self.plugins:
            self._logger.info(f'Applying {plugin["plugin"].pluginname}: '
                              f'{await plugin["plugin"].run()}')
            plugin["name"] = plugin["plugin"].pluginname

    def __walk_package(self, package):
        """Recursively walk the supplied package to retrieve all plugins
        """
        try:
            imported_package = __import__(package, fromlist=['MAD'])

            for _, pluginname, ispkg in pkgutil.iter_modules(imported_package.__path__,
                                                             imported_package.__name__ + '.'):
                if not ispkg:
                    plugin_module = __import__(pluginname, fromlist=['MAD'])
                    clsmembers = inspect.getmembers(plugin_module, inspect.isclass)
                    for (_, plugin) in clsmembers:
                        # Only add classes that are a sub class of Plugin, but NOT Plugin itself
                        if issubclass(plugin, Plugin) & (plugin is not Plugin):
                            self._logger.info(f'Found plugin class: {plugin.__name__}')
                            self.plugins.append({"plugin": plugin(self._plugin_subapp, self._mad_parts),
                                                 "path": [package for package in imported_package.__path__][0]})

            # Now that we have looked at all the modules in the current package, start looking
            # recursively for additional modules in sub packages
            all_current_paths = []
            if isinstance(imported_package.__path__, str):
                all_current_paths.append(imported_package.__path__)
            else:
                all_current_paths.extend([x for x in imported_package.__path__])

            for pkg_path in all_current_paths:
                if pkg_path not in self.seen_paths:
                    self.seen_paths.append(pkg_path)

                    # Get all sub directory of the current package path directory
                    child_pkgs = [p for p in os.listdir(pkg_path) if os.path.isdir(os.path.join(pkg_path, p))
                                  and not p.startswith(".")]

                    # For each sub directory, apply the walk_package method recursively
                    for child_pkg in child_pkgs:
                        self.__walk_package(package + '.' + child_pkg)
        except Exception as e:
            self._logger.opt(exception=True).error("Exception in walk_package on package {}: {}", package, e)
