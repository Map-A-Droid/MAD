from flask import (send_from_directory, render_template, request)
from madmin.functions import (auth_required, nocache, get_geofences)
from utils.functions import (generate_path)
from utils.MappingManager import MappingManager
from utils.logging import logger

class path(object):
    def __init__(self, db, args, app, mapping_manager: MappingManager,):
        self._db = db
        self._args = args
        self._app = app
        if self._args.madmin_time == "12":
            self._datetimeformat = '%Y-%m-%d %I:%M:%S %p'
        else:
            self._datetimeformat = '%Y-%m-%d %H:%M:%S'
            self._mapping_manager = mapping_manager
        self.add_route()

    def add_route(self):
        routes = [
            ("/screenshot/<path:path>", self.pushscreens),
            ("/static/<path:path>", self.pushstatic),
            ("/gym_img/<path:path>", self.pushGyms),
            ("/screenshots/<path:path>", self.pushScreens),
            ("/asset/<path:path>", self.pushAssets),
            ("/screens", self.screens),
            ("/", self.root),
            ("/raids", self.raids),
            ("/gyms", self.gyms),
            ("/unknown", self.unknown),
            ("/quests", self.quest),
            ("/quests_pub", self.quest_pub)
        ]
        for route, view_func in routes:
            self._app.route(route)(view_func)

    @auth_required
    @nocache
    def pushscreens(self, path):
        return send_from_directory(generate_path(self._args.temp_path), path)

    @auth_required
    def pushstatic(self, path):
        return send_from_directory(generate_path('madmin/static'), path)

    @auth_required
    def pushGyms(self, path):
        return send_from_directory('../ocr/gym_img', path)

    @auth_required
    def pushScreens(self, path):
        return send_from_directory('../' + self._args.raidscreen_path, path)

    @auth_required
    def pushAssets(self, path):
        return send_from_directory(self._args.pogoasset, path)

    @auth_required
    def screens(self):
        return render_template('screens.html', responsive=str(self._args.madmin_noresponsive).lower(),
                               title="show success Screens")

    @auth_required
    def root(self):
        return render_template('index.html')

    @auth_required
    def raids(self):
        return render_template('raids.html', sort=str(self._args.madmin_sort),
                               responsive=str(self._args.madmin_noresponsive).lower(),
                               title="show Raid Matching")

    @auth_required
    def gyms(self):
        return render_template('gyms.html', sort=self._args.madmin_sort,
                               responsive=str(self._args.madmin_noresponsive).lower(),
                               title="show Gym Matching")

    @auth_required
    def unknown(self):
        return render_template('unknown.html', responsive=str(self._args.madmin_noresponsive).lower(),
                               title="show unkown Gym")

    @auth_required
    @logger.catch()
    def quest(self):
        fence = request.args.get("fence", None)
        stop_fences = []
        stop_fences.append('All')
        for possible_fence in get_geofences(self._mapping_manager, 'pokestops'):
            stop_fences.append(possible_fence)
        return render_template('quests.html', pub=False,
                               responsive=str(self._args.madmin_noresponsive).lower(),
                               title="show daily Quests", fence=fence, stop_fences=stop_fences)

    @auth_required
    def quest_pub(self):
        fence = request.args.get("fence", None)
        stop_fences = []
        stop_fences.append('All')
        for fence in get_geofences(self._mapping_manager, 'pokestops'):
            stop_fences.append(fence)
        return render_template('quests.html', pub=True,
                               responsive=str(self._args.madmin_noresponsive).lower(),
                               title="show daily Quests", fence=fence, stop_fences=stop_fences)

