import inspect
import os
import pkgutil


class Plugin(object):
    """Base class that each plugin must inherit from. within this class
    you must define the methods that all of your plugins must implement
    """

    def __init__(self):
        self.description = 'UNKNOWN'

    def perform_operation(self, db_wrapper, args, madmin, logger, data_manager,
                                   mapping_manager, jobstatus, device_Updater, ws_server):
        """The method that we expect all plugins to implement. This is the
        method that our framework will call
        """
        raise NotImplementedError


class PluginCollection(object):
    """Upon creation, this class will read the plugins package for modules
    that contain a class definition that is inheriting from the Plugin class
    """

    def __init__(self, plugin_package, db_wrapper, args, madmin, logger, data_manager,
                                   mapping_manager, jobstatus, device_Updater, ws_server):
        """Constructor that initiates the reading of all available plugins
        when an instance of the PluginCollection object is created
        """
        self.plugin_package = plugin_package
        self._db = db_wrapper
        self._args = args
        self._madmin = madmin
        self._logger = logger
        self._data_manager = data_manager
        self._mapping_manager = mapping_manager
        self._jobstatus = jobstatus
        self._device_Updater = device_Updater
        self._ws_server = ws_server
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
        print()
        self._logger.info(f'Applying all plugins:')
        for plugin in self.plugins:
            self._logger.info(f'Applying {plugin.description} '
                              f'{plugin.perform_operation(self._db , self._args, self._madmin, self._logger, self._data_manager, self._mapping_manager, self._jobstatus, self._device_Updater, self._ws_server)}')

    def walk_package(self, package):
        """Recursively walk the supplied package to retrieve all plugins
        """
        imported_package = __import__(package, fromlist=['blah'])

        for _, pluginname, ispkg in pkgutil.iter_modules(imported_package.__path__, imported_package.__name__ + '.'):
            if not ispkg:
                plugin_module = __import__(pluginname, fromlist=['blah'])
                clsmembers = inspect.getmembers(plugin_module, inspect.isclass)
                for (_, c) in clsmembers:
                    # Only add classes that are a sub class of Plugin, but NOT Plugin itself
                    if issubclass(c, Plugin) & (c is not Plugin):
                        self._logger.info(f'Found plugin class: {c.__name__}')
                        self.plugins.append(c())


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
                child_pkgs = [p for p in os.listdir(pkg_path) if os.path.isdir(os.path.join(pkg_path, p))]

                # For each sub directory, apply the walk_package method recursively
                for child_pkg in child_pkgs:
                    self.walk_package(package + '.' + child_pkg)