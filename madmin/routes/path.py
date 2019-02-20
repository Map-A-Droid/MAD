from flask import (send_from_directory, render_template)
from madmin.functions import (auth_required, nocache)
from utils.functions import (generate_path)


class path(object):
    def __init__(self, db, args, app):
        self._db = db
        self._args = args
        self._app = app
        if self._args.madmin_time == "12":
            self._datetimeformat = '%Y-%m-%d %I:%M:%S %p'
        else:
            self._datetimeformat = '%Y-%m-%d %H:%M:%S'
        self.add_route()

    def add_route(self):
        routes = [
            ("/screenshot/<path:path>", self.pushscreens),
            ("/static/<path:path>", self.pushstatic),
            ("/gym_img/<path:path>", self.pushGyms),
            ("/www_hash/<path:path>", self.pushHashes),
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
    def pushHashes(self, path):
        return send_from_directory('../ocr/www_hash', path)

    @auth_required
    def pushScreens(self, path):
        return send_from_directory('../' + self._args.raidscreen_path, path)

    @auth_required
    def pushAssets(self, path):
        return send_from_directory(self._args.pogoasset, path)

    @auth_required
    def screens(self):
        return render_template('screens.html', responsive=str(self._args.madmin_noresponsive).lower(),
                               title="show success Screens", running_ocr=(self._args.only_ocr))

    @auth_required
    def root(self):
        return render_template('index.html', running_ocr=(self._args.only_ocr))

    @auth_required
    def raids(self):
        return render_template('raids.html', sort=str(self._args.madmin_sort),
                               responsive=str(self._args.madmin_noresponsive).lower(),
                               title="show Raid Matching", running_ocr=(self._args.only_ocr))

    @auth_required
    def gyms(self):
        return render_template('gyms.html', sort=self._args.madmin_sort,
                               responsive=str(self._args.madmin_noresponsive).lower(),
                               title="show Gym Matching", running_ocr=(self._args.only_ocr))

    @auth_required
    def unknown(self):
        return render_template('unknown.html', responsive=str(self._args.madmin_noresponsive).lower(),
                               title="show unkown Gym", running_ocr=(self._args.only_ocr))

    @auth_required
    def quest(self):
        return render_template('quests.html', pub=False,
                               responsive=str(self._args.madmin_noresponsive).lower(),
                               title="show daily Quests", running_ocr=(self._args.only_ocr))

    def quest_pub(self):
        return render_template('quests.html', pub=True,
                               responsive=str(self._args.madmin_noresponsive).lower(),
                               title="show daily Quests", running_ocr=(self._args.only_ocr))

