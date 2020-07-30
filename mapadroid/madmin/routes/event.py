from flask import (render_template, request, redirect, url_for, jsonify, flash)
from flask_caching import Cache
from datetime import datetime
from mapadroid.madmin.functions import auth_required
from mapadroid.utils.MappingManager import MappingManager


cache = Cache(config={'CACHE_TYPE': 'simple'})


class MADminEvent(object):
    def __init__(self, db, args, logger, app, mapping_manager: MappingManager, data_manager):
        self._db = db
        self._args = args
        if self._args.madmin_time == "12":
            self._datetimeformat = '%Y-%m-%d %I:%M:%S %p'
        else:
            self._datetimeformat = '%Y-%m-%d %H:%M:%S'
        self._ws_connected_phones: list = []
        self._data_manager = data_manager
        self._app = app
        self._app.config["TEMPLATES_AUTO_RELOAD"] = True
        cache.init_app(self._app)
        self._mapping_mananger = mapping_manager

    def add_route(self):
        routes = [
            ("/events", self.events),
            ("/get_events", self.get_events),
            ("/edit_event", self.edit_event),
            ("/save_event", self.save_event),
            ("/del_event", self.del_event)
        ]
        for route, view_func in routes:
            self._app.route(route, methods=['GET', 'POST'])(view_func)

    def start_modul(self):
        self.add_route()

    @auth_required
    def get_events(self):
        data = self._db.get_events()
        events = []
        for dat in data:
            events.append({
                'id': str(dat['id']),
                'event_name': str(dat['event_name']),
                'event_start': str(dat['event_start']),
                'event_end': str(dat['event_end']),
                'event_lure_duration': str(dat['event_lure_duration']),
                'locked': str(dat['locked'])
            })

        return jsonify(events)

    @auth_required
    def events(self):
        return render_template('events.html', title="MAD Events",
                               time=self._args.madmin_time,
                               responsive=str(self._args.madmin_noresponsive).lower())

    @auth_required
    def edit_event(self):

        event_id = request.args.get("id", None)
        event_name: str = ""
        event_start_date: str = ""
        event_start_time: str = ""
        event_end_date: str = ""
        event_end_time: str = ""
        event_lure_duration: int = ""
        if event_id is not None:
            data = self._db.get_events(event_id=event_id)
            event_name = data[0]['event_name']
            event_lure_duration = data[0]['event_lure_duration']
            event_start_date = datetime.strftime(data[0]['event_start'], '%Y-%m-%d')
            event_start_time = datetime.strftime(data[0]['event_start'], '%H:%M')
            event_end_date = datetime.strftime(data[0]['event_end'], '%Y-%m-%d')
            event_end_time = datetime.strftime(data[0]['event_end'], '%H:%M')
        return render_template('event_edit.html', title="MAD Add/Edit Event",
                               time=self._args.madmin_time,
                               responsive=str(self._args.madmin_noresponsive).lower(),
                               event_name=event_name,
                               event_start_date=event_start_date,
                               event_start_time=event_start_time,
                               event_end_date=event_end_date,
                               event_end_time=event_end_time,
                               event_lure_duration=event_lure_duration,
                               id=event_id)

    @auth_required
    def save_event(self):
        event_id = request.form.get("id", None)
        event_name = request.form.get("event_name", None)
        event_start_date = request.form.get("event_start_date", None)
        event_start_time = request.form.get("event_start_time", None)
        event_end_date = request.form.get("event_end_date", None)
        event_end_time = request.form.get("event_end_time", None)
        event_lure_duration = request.form.get("event_lure_duration", None)
        # default lure duration = 30 (min)
        if event_lure_duration == "":
            event_lure_duration = 30
        if event_name == "" or event_start_date == "" or event_start_time == "" or event_end_date == "" \
           or event_end_time == "":
            flash('Error while adding this event')
            return redirect(url_for('events'), code=302)

        self._db.save_event(event_name, event_start_date + " " + event_start_time,
                            event_end_date + " " + event_end_time, event_lure_duration=event_lure_duration, id=event_id)

        flash('Successfully added this event')

        return redirect(url_for('events'), code=302)

    @auth_required
    def del_event(self):
        event_id = request.args.get("id", None)
        if event_id is not None:
            if self._db.delete_event(id=event_id):
                flash('Successfully deleted this event')
                return redirect(url_for('events'), code=302)
            else:
                flash('Could not delete this event')
                return redirect(url_for('events'), code=302)
