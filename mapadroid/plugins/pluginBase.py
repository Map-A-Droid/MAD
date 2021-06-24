import configparser
import inspect
import os
import pkgutil
from aiohttp import web

from mapadroid.plugins.endpoints import register_plugin_endpoints


class Plugin(object):
    """Base class that each plugin must inherit from. within this class
    you must define the methods that all of your plugins must implement
    """

    def __init__(self, mad):

        self.description = 'UNKNOWN'
        self.pluginname = 'UNKNOWN'
        self._pluginconfig = configparser.ConfigParser()
        self._versionconfig = configparser.ConfigParser()

    def perform_operation(self):
        """The method that we expect all plugins to implement. This is the
        method that our framework will call
        """
        raise NotImplementedError


class PluginCollection(object):
    """Upon creation, this class will read the plugins package for modules
    that contain a class definition that is inheriting from the Plugin class
    """

    def __init__(self, plugin_package, mad):
        """Constructor that initiates the reading of all available plugins
        when an instance of the PluginCollection object is created
        """
        self.plugins = []
        self.seen_paths = []

        self.plugin_package = plugin_package
        self._mad = mad
        self._logger = mad['logger']
        self._plugin_subapp = web.Application()
        self._plugin_subapp["plugin_package"] = plugin_package
        self._plugin_subapp["plugins"] = self.plugins
        self._plugin_subapp['db_wrapper'] = mad["db_wrapper"]
        self._plugin_subapp['mad_args'] = mad["args"]
        self._plugin_subapp['mapping_manager'] = mad["mapping_manager"]
        self._plugin_subapp['websocket_server'] = mad["ws_server"]
        self._plugin_subapp["plugin_hotlink"] = self._mad['madmin'].get_plugin_hotlink()
        self._plugin_subapp["storage_obj"] = mad["storage_elem"]
        self._plugin_subapp['device_updater'] = mad["device_Updater"]
        register_plugin_endpoints(self._plugin_subapp)

        self._mad['madmin'].register_plugin("custom_plugins", self._plugin_subapp)

        self.reload_plugins()

    def reload_plugins(self):
        """Reset the list of all plugins and initiate the walk over the main
        provided plugin package to load all available plugins
        """
        self.plugins = []
        self.seen_paths = []

        self._logger.info(f'Looking for plugins under package {self.plugin_package}')
        self.walk_package(self.plugin_package)

    def apply_all_plugins_on_value(self):
        """Apply all of the plugins on the argument supplied to this function
        """
        for plugin in self.plugins:
            self._logger.info(f'Applying {plugin["plugin"].pluginname}: '
                              f'{plugin["plugin"].perform_operation()}')
            plugin["name"] = plugin["plugin"].pluginname

    def walk_package(self, package):
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
                            self.plugins.append({"plugin": plugin(self._mad),
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
                        self.walk_package(package + '.' + child_pkg)
        except Exception as e:
            self._logger.opt(exception=True).error("Exception in walk_package on package {}: {}", package, e)
