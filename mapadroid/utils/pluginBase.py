import inspect
import os
import pkgutil
import configparser
import zipfile

from werkzeug.utils import secure_filename
from flask import Blueprint, request, flash, redirect, url_for
from mapadroid.madmin.functions import auth_required

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

        self._routes = [
            ("/upload_plugin", self.upload_plugin)
        ]

        self.plugin_package = plugin_package
        self._mad = mad
        self._logger = mad['logger']
        self._controller = Blueprint(str("MAD_Plugin_Controller"), __name__)

        for route, view_func in self._routes:
            self._controller.route(route, methods=['GET', 'POST'])(view_func)

        self._mad['madmin'].register_plugin(self._controller)

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
            self._logger.info(f'Applying {plugin.pluginname}: '
                              f'{plugin.perform_operation()}')

    def walk_package(self, package):
        """Recursively walk the supplied package to retrieve all plugins
        """
        imported_package = __import__(package, fromlist=['MAD'])

        for _, pluginname, ispkg in pkgutil.iter_modules(imported_package.__path__, imported_package.__name__ + '.'):
            if not ispkg:
                plugin_module = __import__(pluginname, fromlist=['MAD'])
                clsmembers = inspect.getmembers(plugin_module, inspect.isclass)
                for (_, c) in clsmembers:
                    # Only add classes that are a sub class of Plugin, but NOT Plugin itself
                    if issubclass(c, Plugin) & (c is not Plugin):
                        self._logger.info(f'Found plugin class: {c.__name__}')
                        self.plugins.append(c(self._mad))


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

    def zip_plugin(self, plugin_name):
        plugin_file = os.path.join(self._mad['args'].temp_path, str(plugin_name) + '.mpl')
        plugin_filepath = os.path.join(self.plugin_package, str(plugin_name))

        if not os.path.isdir(plugin_filepath):
            self._logger.error("Plugin folder does not exists - abort")
            return None

        zipobj = zipfile.ZipFile(plugin_file, 'w', zipfile.ZIP_DEFLATED)
        rootlen = len(plugin_filepath) + 1
        for base, dirs, files in os.walk(plugin_filepath):
            if "__pycache__" not in base:
                for file in files:
                    if file != "plugin.ini":
                        fn = os.path.join(base, file)
                        zipobj.write(fn, fn[rootlen:])

        return plugin_file

    def unzip_plugin(self, mpl_file):
        base = os.path.basename(mpl_file)
        try:
            with zipfile.ZipFile(mpl_file, 'r') as zip_ref:
                zip_ref.extractall(os.path.join(self.plugin_package, str(os.path.splitext(base)[0])))
        except:
            self._logger.error("Cannot install new plugin: " + str(mpl_file))
            return False
        return True

    @auth_required
    def upload_plugin(self):
        if request.method == 'POST':
            # check if the post request has the file part
            if 'file' not in request.files:
                flash('No file part')
                return redirect(url_for('plugins'), code=302)
            file = request.files['file']
            if file.filename == '':
                flash('No file selected for uploading')
                return redirect(url_for('plugins'), code=302)
            if file and '.' in file.filename and file.filename.rsplit('.', 1)[1].lower() in ['mpl']:
                filename = secure_filename(file.filename)
                file.save(os.path.join(self._mad['args'].temp_path, filename))
                if self.unzip_plugin(os.path.join(self._mad['args'].temp_path, filename)):
                    flash('Plugin uploaded successfully - check plugin.ini and restart MAD now!')
                return redirect(url_for('plugins'), code=302)
            else:
                flash('Allowed file type is mpl only!')
                return redirect(url_for('plugins'), code=302)

