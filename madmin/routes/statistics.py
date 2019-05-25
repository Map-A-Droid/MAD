import datetime
import json
from flask import (jsonify, render_template, request)
from madmin.functions import auth_required
from utils.language import i8ln
from utils.gamemechanicutil import calculate_mon_level, calculate_iv, get_raid_boss_cp
from utils.geo import get_distance_of_two_points_in_meters


class statistics(object):
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
            ("/statistics", self.statistics),
            ("/get_game_stats", self.game_stats),
            ("/statistics_detection_worker_data", self.statistics_detection_worker_data),
            ("/statistics_detection_worker", self.statistics_detection_worker),
            ("/status", self.status),
            ("/get_status", self.get_status)
        ]
        for route, view_func in routes:
            self._app.route(route)(view_func)

    @auth_required
    def statistics(self):
        minutes_usage = request.args.get('minutes_usage')
        if not minutes_usage:
            minutes_usage = 120
        minutes_spawn = request.args.get('minutes_spawn')
        if not minutes_spawn:
            minutes_spawn = 120

        return render_template('statistics.html', title="MAD Statisics", minutes_spawn=minutes_spawn,
                               minutes_usage=minutes_usage, time=self._args.madmin_time, running_ocr=self._args.only_ocr,
                               responsive=str(self._args.madmin_noresponsive).lower())

    @auth_required
    def game_stats(self):
        minutes_usage = request.args.get('minutes_usage', 10)
        minutes_spawn = request.args.get('minutes_spawn', 10)

        data = self._db.statistics_get_location_info()
        location_info = []
        for dat in data:
            location_info.append({'worker': str(dat[0]), 'locations': str(dat[1]), 'locationsok': str(dat[2]),
                                  'locationsnok': str(dat[3]), 'ratio': str(dat[4]), })

        # empty scans
        data = self._db.statistics_get_all_empty_scanns()
        detection_empty = []
        for dat in data:
            detection_empty.append({'lat': str(dat[1]), 'lng': str(dat[2]), 'worker': str(dat[3]),
                                    'count': str(dat[0]), 'type': str(dat[4]), 'lastscan': str(dat[5]),
                                    'countsuccess': str(dat[6])})

        # statistics_get_detection_count
        data = self._db.statistics_get_detection_count(grouped=False)
        detection = []
        for dat in data:
            detection.append({'worker': str(dat[1]), 'mons': str(dat[2]), 'mons_iv': str(dat[3]),
                              'raids': str(dat[4]), 'quests': str(dat[5])})

        # Stop
        stop = []
        data = self._db.statistics_get_stop_quest()
        for dat in data:
            stop.append({'label': dat[0], 'data': dat[1]})

        # Quest
        quest = self._db.statistics_get_quests_count(1)

        # Usage
        insta = {}
        usage = []
        idx = 0
        usa = self._db.statistics_get_usage_count(minutes_usage)

        for dat in usa:
            if 'CPU-' + dat[4] not in insta:
                insta['CPU-' + dat[4]] = {}
                insta['CPU-' + dat[4]]["axis"] = 1
                insta['CPU-' + dat[4]]["data"] = []
            if 'MEM-' + dat[4] not in insta:
                insta['MEM-' + dat[4]] = {}
                insta['MEM-' + dat[4]]['axis'] = 2
                insta['MEM-' + dat[4]]["data"] = []
            if self._args.stat_gc:
                if 'CO-' + dat[4] not in insta:
                    insta['CO-' + dat[4]] = {}
                    insta['CO-' + dat[4]]['axis'] = 3
                    insta['CO-' + dat[4]]["data"] = []

            insta['CPU-' + dat[4]]['data'].append([dat[3] * 1000, dat[0]])
            insta['MEM-' + dat[4]]['data'].append([dat[3] * 1000, dat[1]])
            if self._args.stat_gc:
                insta['CO-' + dat[4]]['data'].append([dat[3] * 1000, dat[2]])

        for label in insta:
            usage.append(
                {'label': label, 'data': insta[label]['data'], 'yaxis': insta[label]['axis'], 'idx': idx})
            idx += 1

        # Gym
        gym = []
        data = self._db.statistics_get_gym_count()
        for dat in data:
            if dat[0] == 'WHITE':
                color = '#999999'
                text = 'Uncontested'
            elif dat[0] == 'BLUE':
                color = '#0051CF'
                text = 'Mystic'
            elif dat[0] == 'RED':
                color = '#FF260E'
                text = 'Valor'
            elif dat[0] == 'YELLOW':
                color = '#FECC23'
                text = 'Instinct'
            gym.append({'label': text, 'data': dat[1], 'color': color})

        # Spawn
        iv = []
        noniv = []
        sum = []
        sumup = {}

        data = self._db.statistics_get_pokemon_count(minutes_spawn)
        for dat in data:
            if dat[2] == 1:
                iv.append([(dat[0] * 1000), dat[1]])
            else:
                noniv.append([(dat[0] * 1000), dat[1]])

            if (dat[0] * 1000) in sumup:
                sumup[(dat[0] * 1000)] += dat[1]
            else:
                sumup[(dat[0] * 1000)] = dat[1]

        for dat in sumup:
            sum.append([dat, sumup[dat]])

        spawn = {'iv': iv, 'noniv': noniv, 'sum': sum}

        # good_spawns avg
        good_spawns = []
        shiny_spawns = []
        data = self._db.get_best_pokemon_spawns()
        shinyData = self._db.get_shiny_pokemon_spawns()
        for dat in data:
            mon = "%03d" % dat[2]
            monPic = 'asset/pokemon_icons/pokemon_icon_' + mon + '_00.png'
            monName_raw = (get_raid_boss_cp(dat[2]))
            monName = i8ln(monName_raw['name'])
            if self._args.db_method == "rm":
                lvl = calculate_mon_level(dat[7])
            else:
                lvl = dat[7]
            good_spawns.append({'id': dat[2], 'iv': round(calculate_iv(dat[4], dat[5], dat[6]), 0),
                                'lvl': lvl, 'cp': dat[8], 'img': monPic,
                                'name': monName,
                                'periode': datetime.datetime.fromtimestamp(dat[3]).strftime(self._datetimeformat)})
        for dat in shinyData:
            mon = "%03d" % dat[2]
            monPic = 'asset/pokemon_icons/pokemon_icon_' + mon + '_00.png'
            monName_raw = (get_raid_boss_cp(dat[2]))
            monName = i8ln(monName_raw['name'])
            if self._args.db_method == "rm":
                lvl = calculate_mon_level(dat[7])
            else:
                lvl = dat[7]
            shiny_spawns.append({'id': dat[2], 'iv': round(calculate_iv(dat[4], dat[5], dat[6]), 0), 'shiny': data[9],
                                'lvl': lvl, 'cp': dat[8], 'img': monPic,
                                'name': monName,
                                'periode': datetime.datetime.fromtimestamp(dat[3]).strftime(self._datetimeformat)})

        stats = {'spawn': spawn, 'gym': gym, 'detection': detection, 'detection_empty': detection_empty,
                 'quest': quest, 'stop': stop, 'usage': usage, 'good_spawns': good_spawns,
                 'location_info': location_info,'shiny_spawns': shiny_spawns,}
        return jsonify(stats)

    @auth_required
    def statistics_detection_worker_data(self):
        minutes = request.args.get('minutes', 120)
        worker = request.args.get('worker')

        # spawns
        mon = []
        mon_iv = []
        raid = []
        quest = []
        usage = []

        data = self._db.statistics_get_detection_count(minutes=minutes, worker=worker)
        for dat in data:
            mon.append([dat[0] * 1000, int(dat[2])])
            mon_iv.append([dat[0] * 1000, int(dat[3])])
            raid.append([dat[0] * 1000, int(dat[4])])
            quest.append([dat[0] * 1000, int(dat[5])])

        usage.append({'label': 'Mon', 'data': mon})
        usage.append({'label': 'Mon_IV', 'data': mon_iv})
        usage.append({'label': 'Raid', 'data': raid})
        usage.append({'label': 'Quest', 'data': quest})

        # locations avg
        locations_avg = []

        data = self._db.statistics_get_avg_data_time(minutes=minutes, worker=worker)
        for dat in data:
            dtime = datetime.datetime.fromtimestamp(dat[0]).strftime(self._datetimeformat)
            locations_avg.append({'dtime': dtime, 'ok_locations': dat[3], 'avg_datareceive': float(dat[4]),
                                  'transporttype': dat[1], 'type': dat[5]})

        # locations
        ok = []
        nok = []
        sumloc = []
        locations = []
        data = self._db.statistics_get_locations(minutes=minutes, worker=worker)
        for dat in data:
            ok.append([dat[0] * 1000, int(dat[3])])
            nok.append([dat[0] * 1000, int(dat[4])])
            sumloc.append([dat[0] * 1000, int(dat[2])])

        locations.append({'label': 'Locations', 'data': sumloc})
        locations.append({'label': 'Locations_ok', 'data': ok})
        locations.append({'label': 'Locations_nok', 'data': nok})

        # dataratio
        loctionratio = []
        data = self._db.statistics_get_locations_dataratio(minutes=minutes, worker=worker)
        if len(data) > 0:
            for dat in data:
                loctionratio.append({'label': dat[3], 'data': dat[2]})
        else:
            loctionratio.append({'label': '', 'data': 0})

        # all spawns
        all_spawns = []
        data = self._db.statistics_get_detection_count(grouped=False, worker=worker)
        all_spawns.append({'type': 'Mon', 'amount': int(data[0][2])})
        all_spawns.append({'type': 'Mon_IV', 'amount': int(data[0][3])})
        all_spawns.append({'type': 'Raid', 'amount': int(data[0][4])})
        all_spawns.append({'type': 'Quest', 'amount': int(data[0][5])})

        # raw detection data
        detections_raw = []
        data = self._db.statistics_get_detection_raw(minutes=minutes, worker=worker)
        for dat in data:
            detections_raw.append({'type': dat[1], 'id': dat[2], 'count': dat[3]})

        # location raw
        location_raw = []
        last_lat = 0
        last_lng = 0
        distance = 0
        data = self._db.statistics_get_location_raw(minutes=minutes, worker=worker)
        for dat in data:
            if last_lat != 0 and last_lng != 0:
                distance = round(get_distance_of_two_points_in_meters(last_lat, last_lng, dat[1], dat[2]), 2)
                last_lat = dat[1]
                last_lng = dat[2]
            if last_lat == 0 and last_lng == 0:
                last_lat = dat[1]
                last_lng = dat[2]
            if dat[1] == 0 and dat[2] == 0:
                distance = ''

            location_raw.append({'lat': dat[1], 'lng': dat[2], 'distance': distance, 'type': dat[3], 'data': dat[4],
                                 'fix_ts': datetime.datetime.fromtimestamp(dat[5]).strftime(self._datetimeformat),
                                 'data_ts': datetime.datetime.fromtimestamp(dat[6]).strftime(self._datetimeformat),
                                 'transporttype': dat[8]})

        workerstats = {'avg': locations_avg, 'receiving': usage, 'locations': locations,
                       'ratio': loctionratio, 'allspawns': all_spawns, 'detections_raw': detections_raw,
                       'location_raw': location_raw}
        return jsonify(workerstats)

    @auth_required
    def statistics_detection_worker(self):
        minutes = request.args.get('minutes', 120)
        worker = request.args.get('worker')

        return render_template('statistics_worker.html', title="MAD Worker Statisics", minutes=minutes,
                               time=self._args.madmin_time, worker=worker, running_ocr=self._args.only_ocr,
                               responsive=str(self._args.madmin_noresponsive).lower())

    @auth_required
    def status(self):
        return render_template('status.html', responsive=str(self._args.madmin_noresponsive).lower(),
                               title="Worker status",
                               running_ocr=(self._args.only_ocr))

    @auth_required
    def get_status(self):
        data = json.loads(self._db.download_status())
        return jsonify(data)
