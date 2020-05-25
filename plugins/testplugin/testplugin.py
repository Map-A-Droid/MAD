import mapadroid.utils.pluginBase
from flask import render_template, Blueprint


class Testplugin(mapadroid.utils.pluginBase.Plugin):
    """This plugin is just the identity function: it returns the argument
    """
    def __init__(self):
        super().__init__()
        self.description = "Test Plugin - MAD 1"
        self.pluginname = "testplugin"

        self.staticpath = None
        self.templatepath = None
        self._db = None
        self._args = None
        self._madmin = None
        self._logger = None
        self._data_manager = None
        self._mapping_manager = None
        self._jobstatus = None
        self._device_Updater = None
        self._ws_server = None

        self._routes = [
            ("/testplugin", self.test),
        ]

        self._hotlink = [
            ("Show Stops from DB", "/testplugin"),
        ]

    def perform_operation(self, db_wrapper, args, madmin, logger, data_manager,
                          mapping_manager, jobstatus, device_Updater, ws_server):
        """The actual implementation of the identity plugin is to just return the
        argument
        """

        # do not change this part ▽▽▽▽▽▽▽▽▽▽▽▽▽▽▽

        self._db = db_wrapper
        self._args = args
        self._madmin = madmin
        self._logger = logger
        self._data_manager = data_manager
        self._mapping_manager = mapping_manager
        self._jobstatus = jobstatus
        self._device_Updater = device_Updater
        self._ws_server = ws_server

        self.staticpath = self._madmin.get_routepath() + "/../../plugins/" + str(self.pluginname) + "/static/"
        self.templatepath = self._madmin.get_routepath() + "/../../plugins/" + str(self.pluginname) + "/template/"

        plugin = Blueprint(str(self.pluginname), __name__, static_folder=self.staticpath,
                           template_folder=self.templatepath)

        for route, view_func in self._routes:
            plugin.route(route, methods=['GET', 'POST'])(view_func)

        for name, link in self._hotlink:
            self._madmin.add_plugin_hotlink(name, link, self.pluginname, self.description)

        # register plugin to MAD Madmin
        self._madmin.register_plugin(plugin)

        # do not change this part △△△△△△△△△△△△△△△

        # load other functions with plugin init

        return True

    def test(self):
        testquery = str(self._db.stops_from_db())
        return render_template("testfile.html",
                               header="Test Plugin", title="Test Plugin",
                               testdata=testquery
                               )
