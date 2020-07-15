import inspect
import os
import base64
import json
import pkgutil
import configparser
import zipfile

from werkzeug.utils import secure_filename
from flask import Blueprint, request, flash, redirect, url_for, send_file
from mapadroid.madmin.functions import auth_required
from mapadroid.utils.functions import generate_path


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
            ("/upload_plugin", self.upload_plugin),
            ("/download_plugin", self.download_plugin),
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
            self._logger.info(f'Applying {plugin["plugin"].pluginname}: '
                              f'{plugin["plugin"].perform_operation()}')
            plugin["name"] = plugin["plugin"].pluginname

    def walk_package(self, package):
        """Recursively walk the supplied package to retrieve all plugins
        """
        imported_package = __import__(package, fromlist=['MAD'])

        for _, pluginname, ispkg in pkgutil.iter_modules(imported_package.__path__, imported_package.__name__ + '.'):
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
                child_pkgs = [p for p in os.listdir(pkg_path) if os.path.isdir(os.path.join(pkg_path, p))]

                # For each sub directory, apply the walk_package method recursively
                for child_pkg in child_pkgs:
                    self.walk_package(package + '.' + child_pkg)

    def zip_plugin(self, plugin_name, folder, version):
        plugin_file_temp = os.path.join(self._mad['args'].temp_path, str(plugin_name) + '.tmp')
        plugin_file = os.path.join(self._mad['args'].temp_path, str(plugin_name) + '.mp')
        if not os.path.isdir(folder):
            self._logger.error("Plugin folder does not exists - abort")
            return None

        if os.path.isfile(plugin_file):
            os.remove(plugin_file)

        if os.path.isfile(plugin_file_temp):
            os.remove(plugin_file_temp)

        zipobj = zipfile.ZipFile(plugin_file_temp, 'w', zipfile.ZIP_DEFLATED)
        rootlen = len(folder) + 1
        for base, _, files in os.walk(folder):
            if "__pycache__" not in base:
                for plugin_file in files:
                    if plugin_file != "plugin.ini":
                        fn = os.path.join(base, plugin_file)
                        zipobj.write(fn, fn[rootlen:])

        zipobj.close()

        with open(plugin_file_temp, mode='rb') as plugin_zip:
            plugin_contents = plugin_zip.read()

        plugin_dict = {"plugin_name": plugin_name, "plugin_content": base64.b64encode(plugin_contents).decode('utf-8'),
                       "plugin_version": version}

        with open(plugin_file, 'w') as plugin_export:
            plugin_export.write(json.dumps(plugin_dict))

        os.remove(plugin_file_temp)

        return plugin_file

    def unzip_plugin(self, mpl_file):

        base = os.path.basename(mpl_file)
        plugin_tmp_zip = mpl_file + ".zip"
        self._logger.info("Try to install/update plugin: " + str(base))

        try:
            with open(mpl_file) as plugin_file:
                data = json.load(plugin_file)
        except (TypeError, ValueError):
            self._logger.error("Old or wrong plugin format - abort")
            return False
        else:
            pass

        plugin_content = base64.b64decode(data['plugin_content'])
        plugin_meta_name = data['plugin_name']
        plugin_version = data['plugin_version']

        tmp_plugin = open(plugin_tmp_zip, "wb")
        tmp_plugin.write(bytearray(plugin_content))
        tmp_plugin.close()

        extractpath = os.path.join(self.plugin_package, plugin_meta_name)
        self._logger.debug("Plugin base path: " + str(base))
        self._logger.debug("Plugin extract path: " + str(extractpath))

        installed_version = None

        if os.path.isfile(extractpath + str("/version.mpl")):
            installed_version = self.get_plugin_version(str(extractpath))

        if installed_version is not None and plugin_version == installed_version:
            self._logger.warning("Plugin version already installed - abort")
            return False

        try:
            with zipfile.ZipFile(plugin_tmp_zip, 'r') as zip_ref:
                zip_ref.extractall(extractpath)

            os.remove(plugin_tmp_zip)

            # check for plugin.ini.example
            if not os.path.isfile(
                    os.path.join(extractpath, "plugin.ini.example")):
                self._logger.debug("Creating basic plugin.ini.example")
                with open(os.path.join(extractpath, "plugin.ini.example"), 'w') as pluginini:
                    pluginini.write('[plugin]\n')
                    pluginini.write('active = false\n')
        except:  # noqa: E722
            self._logger.opt(exception=True).error("Cannot install new plugin: " + str(mpl_file))
            return False

        self._logger.info("Installation successfully")
        return True

    @auth_required
    def upload_plugin(self):
        if request.method == 'POST':
            # check if the post request has the file part
            if 'file' not in request.files:
                flash('No file part')
                return redirect(url_for('plugins'), code=302)
            plugin_file = request.files['file']
            if plugin_file.filename == '':
                flash('No file selected for uploading')
                return redirect(url_for('plugins'), code=302)
            if plugin_file and '.' in plugin_file.filename and \
                    plugin_file.filename.rsplit('.', 1)[1].lower() in ['mp']:
                filename = secure_filename(plugin_file.filename)
                plugin_file.save(os.path.join(self._mad['args'].temp_path, filename))
                if self.unzip_plugin(os.path.join(self._mad['args'].temp_path, filename)):
                    flash('Plugin uploaded successfully - check plugin.ini and restart MAD now!')
                else:
                    flash('Error while installation - check MAD log.')
                return redirect(url_for('plugins'), code=302)
            else:
                flash('Allowed file type is mp only!')
                return redirect(url_for('plugins'), code=302)

    @auth_required
    def download_plugin(self):
        plugin = request.args.get("plugin", None)
        if plugin is None:
            return redirect(url_for('plugins'), code=302)

        mad_plugin = next((item for item in self.plugins if item["name"] == plugin), None)
        if mad_plugin is None:
            return redirect(url_for('plugins'), code=302)

        mp_file = self.zip_plugin(plugin, mad_plugin['path'], self.get_plugin_version(mad_plugin['path']))
        if mp_file is None:
            return redirect(url_for('plugins'), code=302)

        return send_file(generate_path(self._mad['args'].temp_path) + "/" + plugin + ".mp",
                         as_attachment=True, attachment_filename=plugin + ".mp", cache_timeout=0)

    @staticmethod
    def get_plugin_version(plugin_folder):
        plugin_config = configparser.ConfigParser()
        plugin_config.read(plugin_folder + "/version.mpl")
        return plugin_config.get("plugin", "version", fallback="unknown")
