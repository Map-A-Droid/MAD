from flask import render_template, redirect, url_for
from mapadroid.madmin.functions import auth_required
from mapadroid.utils.autoconfig import validate_hopper_ready, RGCConfig, PDConfig


class AutoConfigManager(object):
    def __init__(self, db, app, data_manager, args):
        self._db = db
        self._app = app
        self._args = args
        self._data_manager = data_manager

    def add_route(self):
        routes = [
            ("/autoconfig", self.autoconfig_root),
            ("/autoconfig/pending", self.autoconfig_pending),
            ("/autoconfig/pending/<int:session_id>", self.autoconfig_pending_dev),
            ("/autoconfig/rgc", self.autoconf_rgc),
            ("/autoconfig/pd", self.autoconf_pd),
            ("/autoconfig/google", self.autoconf_google),
            ("/autoconfig/google/<int:email_id>", self.autoconf_google_single)
        ]
        for route_def in routes:
            if len(route_def) == 2:
                route, view_func = route_def
                self._app.route(route)(view_func)
            elif len(route_def) == 3:
                route, view_func, methods = route_def
                self._app.route(route, methods=methods)(view_func)

    def start_modul(self):
        self.add_route()

    @auth_required
    def autoconf_google(self):
        sql = "SELECT ag.`email_id`, ag.`email`, sd.`device_id`, sd.`name`\n"\
              "FROM `autoconfig_google` ag\n"\
              "LEFT JOIN `settings_device` sd ON sd.`email_id` = ag.`email_id`\n"\
              "WHERE ag.`instance_id` = %s"
        accounts = self._db.autofetch_all(sql, (self._db.instance_id))
        return render_template('autoconfig_google.html',
                               subtab="autoconf_google",
                               accounts=accounts,
                               )

    @auth_required
    def autoconf_google_single(self, email_id):
        if email_id == 0:
            account = {}
            uri = url_for('api_autoconf_google')
        else:
            sql = "SELECT *\n"\
                  "FROM `autoconfig_google`\n"\
                  "WHERE `instance_id` = %s AND `email_id` = %s"
            account = self._db.autofetch_row(sql, (self._db.instance_id, email_id))
            if not account:
                return redirect(url_for('autoconfig_pending'), code=302)
            uri = "{}/{}".format(url_for('api_autoconf_google'), email_id)
        redir_uri = url_for('autoconf_google')
        return render_template('autoconfig_google_single.html',
                               subtab="autoconf_google",
                               element=account,
                               uri=uri,
                               redirect=redir_uri,
                               method='POST'
                               )

    @auth_required
    def autoconf_pd(self):
        config = PDConfig(self._db, self._args, self._data_manager)
        auths = self._data_manager.get_root_resource('auth')
        uri = url_for('api_autoconf_pd')
        return render_template('autoconfig_config_editor.html',
                               subtab="autoconf_pd",
                               config_name='PogoDroid',
                               config_element=config,
                               auths=auths,
                               uri=uri
                               )

    @auth_required
    def autoconfig_pending(self):
        is_ready = validate_hopper_ready(self._data_manager)
        sql = "SELECT count(*)\n"\
              "FROM `autoconfig_google` ag\n"\
              "LEFT JOIN `settings_device` sd ON sd.`email_id` = ag.`email_id`\n"\
              "WHERE ag.`instance_id` = %s AND sd.`device_id` IS NULL"
        has_logins = self._db.autofetch_value(sql, (self._db.instance_id)) > 0
        pending = {}
        sql = "SELECT ar.`session_id`, ar.`ip`, sd.`device_id`, sd.`name` AS 'origin', ar.`status`"\
              "FROM `autoconfig_registration` ar\n"\
              "LEFT JOIN `settings_device` sd ON sd.`device_id` = ar.`device_id`\n"\
              "WHERE ar.`instance_id` = %s"
        data = self._db.autofetch_all(sql, (self._db.instance_id))
        for row in data:
            if row['status'] == 0:
                row['status_hr'] = 'Pending'
            elif row['status'] == 1:
                row['status_hr'] = 'Accepted'
            else:
                row['status_hr'] = 'Rejected'
            pending[row['session_id']] = row
        return render_template('autoconfig_pending.html',
                               subtab="autoconf_dev",
                               pending=pending,
                               is_ready=is_ready,
                               has_logins=has_logins,
                               )

    @auth_required
    def autoconfig_pending_dev(self, session_id):
        sql = "SELECT *\n"\
              "FROM `autoconfig_registration`\n"\
              "WHERE `session_id` = %s AND `instance_id` = %s"
        session = self._db.autofetch_row(sql, (session_id, self._db.instance_id))
        if not session:
            return redirect(url_for('autoconfig_pending'), code=302)
        sql = "SELECT ag.`email_id`, ag.`email`\n"\
              "FROM `autoconfig_google` ag\n"\
              "LEFT JOIN `settings_device` sd ON sd.`email_id` = ag.`email_id`\n"\
              "WHERE ag.`instance_id` = %s AND (sd.`device_id` IS NULL OR sd.`device_id` = %s)"
        google_addresses = self._db.autofetch_all(sql, (self._db.instance_id, session['device_id']))
        devices = self._data_manager.get_root_resource('device')
        uri = "{}/{}".format(url_for('api_autoconf'), session_id)
        redir_uri = url_for('autoconfig_pending')
        return render_template('autoconfig_pending_dev.html',
                               subtab="autoconf_dev",
                               element=session,
                               devices=devices,
                               accounts=google_addresses,
                               uri=uri,
                               redirect=redir_uri,
                               method='POST'
                               )

    @auth_required
    def autoconf_rgc(self):
        config = RGCConfig(self._db, self._args, self._data_manager)
        auths = self._data_manager.get_root_resource('auth')
        uri = url_for('api_autoconf_rgc')
        return render_template('autoconfig_config_editor.html',
                               subtab="autoconf_rgc",
                               config_name='Remote GPS Controller',
                               config_element=config,
                               auths=auths,
                               uri=uri
                               )

    @auth_required
    def autoconfig_root(self):
        return redirect(url_for('autoconfig_pending'), code=302)
