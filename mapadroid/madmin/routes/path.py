from flask import send_from_directory, render_template, request, jsonify, redirect, url_for

from mapadroid.madmin.functions import auth_required, get_quest_areas
from mapadroid.utils import MappingManager
from mapadroid.utils.functions import generate_path
from mapadroid.utils.logging import get_logger, LoggerEnums


logger = get_logger(LoggerEnums.madmin)


class path(object):
    def __init__(self, db, args, app, mapping_manager: MappingManager, jobstatus, data_manager, plugin_hotlink):
        self._db = db
        self._args = args
        self._app = app
        self._jobstatus = jobstatus
        if self._args.madmin_time == "12":
            self._datetimeformat = '%Y-%m-%d %I:%M:%S %p'
        else:
            self._datetimeformat = '%Y-%m-%d %H:%M:%S'
        self._mapping_manager = mapping_manager
        self._data_manager = data_manager
        self._plugin_hotlink = plugin_hotlink

    def add_route(self):
        routes = [
            ("/screenshot/<path:path>", self.pushscreens),
            ("/static/<path:path>", self.pushstatic),
            ("/asset/<path:path>", self.pushAssets),
            ("/", self.root),
            ("/quests", self.quest),
            ("/quests_pub", self.quest_pub),
            ("/pick_worker", self.pickworker),
            ("/jobstatus", self.jobstatus),
            ('/robots.txt', self.send_static_file),
            ("/plugins", self.plugins)
        ]
        for route, view_func in routes:
            self._app.route(route)(view_func)

    def start_modul(self):
        self.add_route()

    @auth_required
    def pushscreens(self, path):
        return send_from_directory(generate_path(self._args.temp_path), path)

    @auth_required
    def pushstatic(self, path):
        return send_from_directory(generate_path('madmin/static'), path)

    @auth_required
    def pushAssets(self, path):
        return send_from_directory(self._args.pogoasset, path)

    @auth_required
    def root(self):
        return redirect(url_for('settings'))

    @auth_required
    @logger.catch()
    def quest(self):
        fence = request.args.get("fence", None)
        stop_fences = get_quest_areas(self._mapping_manager, self._data_manager)
        return render_template('quests.html', pub=False,
                               responsive=str(self._args.madmin_noresponsive).lower(),
                               title="show daily Quests", fence=fence, stop_fences=stop_fences)

    @auth_required
    def quest_pub(self):
        fence = request.args.get("fence", None)
        stop_fences = get_quest_areas(self._mapping_manager, self._data_manager)
        return render_template('quests.html', pub=True,
                               responsive=str(self._args.madmin_noresponsive).lower(),
                               title="show daily Quests", fence=fence, stop_fences=stop_fences)

    @auth_required
    def pickworker(self):
        jobname = request.args.get("jobname", None)
        worker_type = request.args.get("type", None)
        return render_template('workerpicker.html',
                               responsive=str(self._args.madmin_noresponsive).lower(),
                               title="Select Worker", jobname=jobname, type=worker_type)

    @auth_required
    def jobstatus(self):
        return jsonify(self._jobstatus)

    def send_static_file(self):
        return send_from_directory(self._app.static_folder, request.path[1:])

    @auth_required
    def plugins(self):
        plugins = {}

        for plugin in self._plugin_hotlink:
            if plugin['author'] not in plugins:
                plugins[plugin['author']] = {}

            if plugin['Plugin'] not in plugins[plugin['author']]:
                plugins[plugin['author']][plugin['Plugin']] = {}
                plugins[plugin['author']][plugin['Plugin']]['links'] = []

            plugins[plugin['author']][plugin['Plugin']]['authorurl'] = plugin['authorurl']
            plugins[plugin['author']][plugin['Plugin']]['version'] = plugin['version']
            plugins[plugin['author']][plugin['Plugin']]['description'] = plugin['description']
            plugins[plugin['author']][plugin['Plugin']]['links'].append({'linkname': plugin['linkname'],
                                                                         'linkurl': plugin['linkurl'],
                                                                         'description': plugin['linkdescription']})
        return render_template('plugins.html',
                               responsive=str(self._args.madmin_noresponsive).lower(),
                               title="Select Plugin", plugin_hotlinks=plugins)
