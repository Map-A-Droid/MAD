from flask import send_from_directory, render_template, request, jsonify, redirect, url_for

from mapadroid.madmin.functions import auth_required, get_quest_areas, generate_coords_from_geofence
from mapadroid.utils import MappingManager
from mapadroid.utils.functions import generate_path
from mapadroid.utils.logging import logger


class path(object):
    def __init__(self, db, args, app, mapping_manager: MappingManager, jobstatus, data_manager):
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
        self.add_route()

    def add_route(self):
        routes = [
            ("/screenshot/<path:path>", self.pushscreens),
            ("/static/<path:path>", self.pushstatic),
            ("/asset/<path:path>", self.pushAssets),
            ("/", self.root),
            ("/quests", self.quest),
            ("/quests_pub", self.quest_pub),
            ("/utilities", self.utilities),
            ("/utilities/quests", self.util_quests),
            ("/utilities/util_q", self.util_q),
            ("/utilities/stops", self.util_stops),
            ("/utilities/gyms", self.util_gyms),
            ("/utilities/pokemon", self.util_pokemon),
            ("/pick_worker", self.pickworker),
            ("/jobstatus", self.jobstatus),
            ('/robots.txt', self.send_static_file)
        ]
        for route, view_func in routes:
            self._app.route(route)(view_func)

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
        type = request.args.get("type", None)
        return render_template('workerpicker.html',
                               responsive=str(self._args.madmin_noresponsive).lower(),
                               title="Select Worker", jobname=jobname, type=type)

    @auth_required
    def jobstatus(self):
        return jsonify(self._jobstatus)

    def send_static_file(self):
        return send_from_directory(self._app.static_folder, request.path[1:])

    @logger.catch()
    @auth_required
    def util_quests(self):
        fence = request.args.get("fence", None)
        stop_fences = get_quest_areas(self._mapping_manager, self._data_manager)
        return render_template('utilities_quests.html', pub=False,
                               responsive=str(self._args.madmin_noresponsive).lower(),
                               title="Quest Maintenance", subtab='quests', fence=fence, stop_fences=stop_fences)

    @logger.catch()
    @auth_required
    def util_q(self):
        user_fence  = request.args.get("fence", "all")
        timestamp   = request.args.get("beforetime", "none")
        user_action = request.args.get("action", "count") # default to the counting option
        bt = None if timestamp == "none" else timestamp
        dq = True if user_action == "delete" else False
        if user_fence.lower() == "all":
            ff = None
        else:
            ff = generate_coords_from_geofence(self._mapping_manager, self._data_manager, user_fence)

        res = self._db.delete_quests_before_time(before_timestamp=bt, from_fence=ff, delete_quests=dq)

        return ("Deleted " if dq else "Found ") + str(res) + (" quest" + "s" if res != 1 else "")

    @logger.catch()
    @auth_required
    def util_stops(self):
        fence = request.args.get("fence", None)
        stop_fences = get_quest_areas(self._mapping_manager, self._data_manager)
        return render_template('utilities_stops.html', pub=False,
                               responsive=str(self._args.madmin_noresponsive).lower(),
                               title="Pokestop Maintenance", subtab='stops', fence=fence, stop_fences=stop_fences)

    @logger.catch()
    @auth_required
    def util_gyms(self):
        fence = request.args.get("fence", None)
        stop_fences = get_quest_areas(self._mapping_manager, self._data_manager)
        return render_template('utilities_gyms.html', pub=False,
                               responsive=str(self._args.madmin_noresponsive).lower(),
                               title="Gym Maintenance", subtab='gyms', fence=fence, stop_fences=stop_fences)

    @logger.catch()
    @auth_required
    def util_pokemon(self):
        fence = request.args.get("fence", None)
        stop_fences = get_quest_areas(self._mapping_manager, self._data_manager)
        return render_template('utilities_pokemon.html', pub=False,
                               responsive=str(self._args.madmin_noresponsive).lower(),
                               title="Pokemon Maintenance", subtab='pokemon', fence=fence, stop_fences=stop_fences)

    @logger.catch
    @auth_required
    def utilities(self):
        return redirect(url_for('util_quests'), code=302)
