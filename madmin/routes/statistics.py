import datetime
import json
import time
from flask import (jsonify, render_template, request)
from madmin.functions import auth_required, generate_coords_from_geofence, get_geofences
from utils.language import i8ln
from utils.gamemechanicutil import calculate_mon_level, calculate_iv, get_raid_boss_cp, form_mapper
from utils.geo import get_distance_of_two_points_in_meters
from utils.logging import logger


class statistics(object):
    def __init__(self, db, args, app, mapping_manager):
        self._db = db
        self._args = args
        self._app = app
        self._mapping_manager = mapping_manager
        if self._args.madmin_time == "12":
            self._datetimeformat = '%Y-%m-%d %I:%M:%S %p'
        else:
            self._datetimeformat = '%Y-%m-%d %H:%M:%S'
        self.add_route()

    def add_route(self):
        routes = [
            ("/statistics", self.statistics),
            ("/statistics_mon", self.statistics_mon),

            ("/statistics_shiny", self.statistics_shiny),
            ("/get_game_stats_shiny", self.game_stats_shiny_v2),

            ("/get_game_stats", self.game_stats),
            ("/get_game_stats_mon", self.game_stats_mon),
            ("/statistics_detection_worker_data", self.statistics_detection_worker_data),
            ("/statistics_detection_worker", self.statistics_detection_worker),
            ("/status", self.status),
            ("/get_status", self.get_status),
            ("/get_spawnpoints_stats", self.get_spawnpoints_stats),
            ("/statistics_spawns", self.statistics_spawns),
            ("/shiny_stats", self.statistics_shiny),
            ("/shiny_stats_data", self.shiny_stats_data),
        ]
        for route, view_func in routes:
            self._app.route(route)(view_func)

    @auth_required
    def statistics(self):
        minutes_usage = request.args.get('minutes_usage')
        if not minutes_usage:
            minutes_usage = 120

        return render_template('statistics/statistics.html', title="MAD Statisics", minutes_usage=minutes_usage,
                               time=self._args.madmin_time,
                               responsive=str(self._args.madmin_noresponsive).lower())

    @auth_required
    def statistics_mon(self):
        minutes_spawn = request.args.get('minutes_spawn')
        if not minutes_spawn:
            minutes_spawn = 120

        return render_template('statistics/mon_statistics.html', title="MAD Mon Statisics", minutes_spawn=minutes_spawn,
                               time=self._args.madmin_time,
                               responsive=str(self._args.madmin_noresponsive).lower())

    @auth_required
    def statistics_shiny(self):
        return render_template('statistics/shiny_statistics.html', title="MAD Shiny Statisics",
                               time=self._args.madmin_time, running_ocr=self._args.only_ocr,
                               responsive=str(self._args.madmin_noresponsive).lower())

    @auth_required
    def game_stats(self):
        minutes_usage = request.args.get('minutes_usage', 10)

        # statistics_get_detection_count
        data = self._db.statistics_get_detection_count(grouped=False)
        detection = []
        for dat in data:
            detection.append({'worker': str(dat[1]), 'mons': str(dat[2]), 'mons_iv': str(dat[3]),
                              'raids': str(dat[4]), 'quests': str(dat[5])})

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

        # Stop
        stop = []
        data = self._db.statistics_get_stop_quest()
        for dat in data:
            stop.append({'label': dat[0], 'data': dat[1]})

        # Quest
        quest: list = []
        quest_db = self._db.statistics_get_quests_count(1)
        for ts, count in quest_db:
            quest_raw = (ts * 1000, count)
            quest.append(quest_raw)

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

        stats = {'gym': gym,  'detection_empty': detection_empty, 'quest': quest, 'stop': stop, 'usage': usage,
                 'location_info': location_info, 'detection': detection}
        return jsonify(stats)

    @logger.catch
    @auth_required
    def game_stats_mon(self):
        minutes_spawn = request.args.get('minutes_spawn', 10)

        # Spawn
        iv = []
        noniv = []
        sumg = []
        sumup = {}

        data = self._db.statistics_get_pokemon_count(minutes_spawn)
        for dat in data:
            if dat[2] == 1:
                iv.append([(self.utc2local(dat[0]) * 1000), dat[1]])
            else:
                noniv.append([(self.utc2local(dat[0]) * 1000), dat[1]])

            if (self.utc2local(dat[0]) * 1000) in sumup:
                sumup[(self.utc2local(dat[0]) * 1000)] += dat[1]
            else:
                sumup[(self.utc2local(dat[0]) * 1000)] = dat[1]

        for dat in sumup:
            sumg.append([dat, sumup[dat]])

        spawn = {'iv': iv, 'noniv': noniv, 'sum': sumg}

        # good_spawns avg
        good_spawns = []
        data = self._db.get_best_pokemon_spawns()
        for dat in data:
            mon = "%03d" % dat[1]
            monPic = 'asset/pokemon_icons/pokemon_icon_' + mon + '_00.png'
            monName_raw = (get_raid_boss_cp(dat[1]))
            monName = i8ln(monName_raw['name'])
            if self._args.db_method == "rm":
                lvl = calculate_mon_level(dat[6])
            else:
                lvl = dat[6]
            good_spawns.append({'id': dat[1], 'iv': round(calculate_iv(dat[3], dat[4], dat[5]), 0),
                                'lvl': lvl, 'cp': dat[7], 'img': monPic,
                                'name': monName,
                                'periode': datetime.datetime.fromtimestamp
                                (self.utc2local(dat[2])).strftime(self._datetimeformat)})

        stats = {'spawn': spawn, 'good_spawns': good_spawns}
        return jsonify(stats)

    @auth_required
    def shiny_stats_data(self):
        # shiny hour

        shiny_hour_temp = {}
        shiny_hour_calc = {}
        shiny_hour = []
        data = self._db.statistics_get_shiny_stats_hour()
        for dat in data:
            if dat[1] not in shiny_hour_temp:
                shiny_hour_temp[dat[1]] = dat[0]

        for dat in shiny_hour_temp:
            if shiny_hour_temp[dat] not in shiny_hour_calc: shiny_hour_calc[shiny_hour_temp[dat]] = 0
            shiny_hour_calc[shiny_hour_temp[dat]] += 1

        for dat in sorted(shiny_hour_calc):
            sht = ([self.utc2local(dat * 60 * 60) * 1000, shiny_hour_calc[dat]])
            shiny_hour.append(sht)

        shiny_stats = []
        shiny_worker = {}
        shiny_avg = {}
        data = self._db.statistics_get_shiny_stats()
        for dat in data:
            form_suffix = "%02d" % form_mapper(dat[2], dat[5])
            mon = "%03d" % dat[2]
            monPic = 'asset/pokemon_icons/pokemon_icon_' + mon + '_' + form_suffix + '_shiny.png'
            monName_raw = (get_raid_boss_cp(dat[2]))
            monName = i8ln(monName_raw['name'])
            diff: int = dat[0]
            if diff == 0:
                logger.warning('No deeper mon stats are possible - not enought data '
                               '(check config.ini // game_stats_raw)')
                diff = 1

            ratio = round(dat[1] * 100 / diff, 2)
            if dat[3] not in shiny_worker: shiny_worker[dat[3]] = 0
            shiny_worker[dat[3]] += dat[1]

            if dat[2] not in shiny_avg: shiny_avg[dat[2]] = {}
            if dat[5] not in shiny_avg[dat[2]]:
                shiny_avg[dat[2]][dat[5]] = {}
                shiny_avg[dat[2]][dat[5]]['total_shiny'] = []
                shiny_avg[dat[2]][dat[5]]['total_nonshiny'] = []

            shiny_avg[dat[2]][dat[5]]['total_shiny'].append(dat[1])
            shiny_avg[dat[2]][dat[5]]['total_nonshiny'].append(diff)

            shiny_stats.append({'sum': dat[0], 'shiny': dat[1], 'img': monPic, 'name': monName, 'ratio': ratio,
                                'worker': dat[3], 'encounterid': dat[4],
                                'periode': datetime.datetime.fromtimestamp
                                (dat[6]).strftime(self._datetimeformat)})

        shiny_stats_avg = []
        for dat in shiny_avg:
            for form_dat in shiny_avg[dat]:
                form_suffix = "%02d" % form_mapper(dat, form_dat)
                mon = "%03d" % dat
                monPic = 'asset/pokemon_icons/pokemon_icon_' + mon + '_' + form_suffix + '_shiny.png'
                monName_raw = (get_raid_boss_cp(dat))
                monName = i8ln(monName_raw['name'])

                total_shiny_encounters = sum(shiny_avg[dat][form_dat]['total_shiny'])
                total_nonshiny_encounters = sum(shiny_avg[dat][form_dat]['total_nonshiny'])
                shiny_avg_click = round(total_nonshiny_encounters / total_shiny_encounters, 0)

                shiny_stats_avg.append(
                    {'name': monName, 'img': monPic, 'total_shiny_encounters': total_shiny_encounters,
                     'total_nonshiny_encounters': total_nonshiny_encounters, 'click_for_shiny': shiny_avg_click})

        shiny_stats_worker = []
        for dat in shiny_worker:
            shiny_stats_worker.append({'sum': shiny_worker[dat], 'worker': dat})

        stats = {'shiny': shiny_stats, 'shiny_worker': shiny_stats_worker,
                 'shiny_hour': shiny_hour, 'shiny_stats_avg': shiny_stats_avg}
        return jsonify(stats)

    @logger.catch
    @auth_required
    def game_stats_shiny_v2(self):
        logger.debug('game_stats_shiny_v2')
        timestamp_from = request.args.get('from', None)
        if (timestamp_from):
            timestamp_from = self.local2utc(int(timestamp_from))
            logger.debug('using timestamp_from: {}', timestamp_from)

        timestamp_to = request.args.get('to', None)
        if (timestamp_to):
            timestamp_to = self.local2utc(int(timestamp_to))
            logger.debug('using timestamp_to: {}', timestamp_to)


        tmp_perworker_v2 = {}
        data = self._db.statistics_get_shiny_stats_v2(timestamp_from, timestamp_to)
        # SELECT pokemon.pokemon_id, pokemon.form, pokemon.latitude, pokemon.longitude, pokemon.gender, pokemon.costume, tr.count, tr.timestamp_scan, tr.worker, pokemon.encounter_id
        found_shiny_mon_id = []
        shiny_count = {}
        mon_names = {}
        tmp_perhour_v2 = {}

        if data is None or len(data) == 0:
             return jsonify({'empty': True});

        shiny_stats_v2 = []
        for dat in data:
            form_suffix = "%02d" % form_mapper(dat[0], dat[1])
            mon = "%03d" % dat[0]
            monPic = 'asset/pokemon_icons/pokemon_icon_' + mon + '_' + form_suffix + '_shiny.png'
            monName_raw = (get_raid_boss_cp(dat[0]))
            monName = i8ln(monName_raw['name'])
            mon_names[dat[0]] = monName
            found_shiny_mon_id.append(mon) # append everything now, we will set() it later to remove duplicates
            if dat[8] not in tmp_perworker_v2:
                tmp_perworker_v2[dat[8]] = 0
            tmp_perworker_v2[dat[8]] += 1

            if dat[0] not in shiny_count:
                 shiny_count[dat[0]] = {}
            if dat[1] not in shiny_count[dat[0]]:
                 shiny_count[dat[0]][dat[1]] = 0
            shiny_count[dat[0]][dat[1]] += 1

            # there is later strftime which converts to local time too, can't use utc2local - it will do double shift
            timestamp = datetime.datetime.fromtimestamp(dat[7])

            if timestamp.hour in tmp_perhour_v2:
                tmp_perhour_v2[timestamp.hour] += 1
            else:
                tmp_perhour_v2[timestamp.hour] = 1

            shiny_stats_v2.append({'img': monPic, 'name': monName, 'worker': dat[8], 'lat': dat[2], 'lat_5': "{:.5f}".format(dat[2]), 'lng_5': "{:.5f}".format(dat[3]), 'lng': dat[3], 'timestamp': timestamp.strftime(self._datetimeformat), 'form': dat[1], 'mon_id': dat[0], 'encounter_id':dat[9]})

        #print(shiny_count)
        global_shiny_stats_v2 = []
        data = self._db.statistics_get_shiny_stats_global_v2(set(found_shiny_mon_id), timestamp_from, timestamp_to)
        for dat in data:
              if dat[1] in shiny_count and dat[2] in shiny_count[dat[1]]:
                  odds = round(dat[0] / shiny_count[dat[1]][dat[2]], 0)
                  form_suffix = "%02d" % form_mapper(dat[1], dat[2])
                  mon = "%03d" % dat[1]
                  monPic = 'asset/pokemon_icons/pokemon_icon_' + mon + '_' + form_suffix + '_shiny.png'
                  global_shiny_stats_v2.append({'name': mon_names[dat[1]], 'count': dat[0], 'img': monPic, 'shiny': shiny_count[dat[1]][dat[2]], 'odds': odds, 'mon_id': dat[1], 'form': dat[2], 'gender': dat[3], 'costume': dat[4]})

        shiny_stats_perworker_v2 = []
        for worker in tmp_perworker_v2:
            shiny_stats_perworker_v2.append({'name': worker, 'count': tmp_perworker_v2[worker]})

        shiny_stats_perhour_v2 = []
        for hour in tmp_perhour_v2:
            shiny_stats_perhour_v2.append([hour, tmp_perhour_v2[hour]])

        stats = {'empty': False, 'shiny_statistics': shiny_stats_v2, 'global_shiny_statistics': global_shiny_stats_v2, 'per_worker': shiny_stats_perworker_v2, 'per_hour': shiny_stats_perhour_v2}
        return jsonify(stats)

    def utc2local(self, ts):
        utc = datetime.datetime.utcnow()
        now = datetime.datetime.now()
        offset = time.mktime(now.timetuple()) - time.mktime(utc.timetuple())
        return ts + offset

    def local2utc(self, ts):
        utc = datetime.datetime.utcnow()
        now = datetime.datetime.now()
        offset = time.mktime(now.timetuple()) - time.mktime(utc.timetuple())
        return ts - offset

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

        # all spaws
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
                               time=self._args.madmin_time, worker=worker,
                               responsive=str(self._args.madmin_noresponsive).lower())

    @auth_required
    def status(self):
        return render_template('status.html', responsive=str(self._args.madmin_noresponsive).lower(),
                               title="Worker status")

    @auth_required
    def get_status(self):
        data = json.loads(self._db.download_status())
        return jsonify(data)

    @auth_required
    @logger.catch()
    def get_spawnpoints_stats(self):

        coords = []
        known = []
        unknown = []
        processed_fences = []

        possible_fences = get_geofences(self._mapping_manager, 'mon_mitm')
        for possible_fence in possible_fences:

            for subfence in possible_fences[possible_fence]['include']:
                if subfence in processed_fences:
                    continue
                processed_fences.append(subfence)
                fence = generate_coords_from_geofence(self._mapping_manager, subfence)
                known.clear()
                unknown.clear()

                data = json.loads(
                    self._db.download_spawns(
                        fence=fence
                    )
                )

                for spawnid in data:
                    if data[str(spawnid)]["endtime"] == None:
                        unknown.append(spawnid)
                    else:
                        known.append(spawnid)
                coords.append({'fence': subfence, 'known': len(known), 'unknown': len(unknown),
                               'sum': len(known) + len(unknown)})

        stats = {'spawnpoints': coords}
        return jsonify(stats)

    @auth_required
    def statistics_spawns(self):
        return render_template('statistics/spawn_statistics.html', title="MAD Spawnpoint Statisics",
                               time=self._args.madmin_time,
                               responsive=str(self._args.madmin_noresponsive).lower())



