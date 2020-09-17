from io import BytesIO
from flask import jsonify, render_template, redirect, url_for, Response, send_file
from mapadroid.madmin.functions import auth_required
from mapadroid.utils.autoconfig import AutoConfIssueGenerator, RGCConfig, PDConfig


class AutoConfigManager(object):
    def __init__(self, db, app, data_manager, args, storage_obj):
        self._db = db
        self._app = app
        self._args = args
        self._data_manager = data_manager
        self._storage_obj = storage_obj

    def add_route(self):
        routes = [
            ("/autoconfig", self.autoconfig_root),
            ("/autoconfig/pending", self.autoconfig_pending),
            ("/autoconfig/pending/<int:session_id>", self.autoconfig_pending_dev),
            ("/autoconfig/logs/<int:session_id>", self.autoconf_logs),
            ("/autoconfig/logs/<int:session_id>/update", self.autoconf_logs_get),
            ("/autoconfig/rgc", self.autoconf_rgc),
            ("/autoconfig/pd", self.autoconf_pd),
            ("/autoconfig/download", self.autoconfig_download_file)
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
    def autoconfig_download_file(self):
        ac_issues = AutoConfIssueGenerator(self._db, self._data_manager, self._args, self._storage_obj)
        if ac_issues.has_blockers():
            return Response('Basic requirements not met', status=406, headers=ac_issues.get_headers())
        pd_conf = PDConfig(self._db, self._args, self._data_manager)
        config_file = BytesIO()
        info = [pd_conf.contents['post_destination']]
        try:
            if pd_conf.contents['mad_auth'] is not None:
                auth = self._data_manager.get_resource('auth', pd_conf.contents['mad_auth'])
                info.append(f"{auth['username']}:{auth['password']}")
        except KeyError:
            # No auth defined for RGC so theres probably no auth for the system
            pass
        config_file.write('\n'.join(info).encode('utf-8'))
        config_file.seek(0, 0)
        return send_file(config_file, as_attachment=True, attachment_filename='mad_autoconf.txt',
                         mimetype='text/plain')

    @auth_required
    def autoconf_logs(self, session_id):
        sql = "SELECT *\n"\
              "FROM `autoconfig_registration`\n"\
              "WHERE `session_id` = %s AND `instance_id` = %s"
        session = self._db.autofetch_row(sql, (session_id, self._db.instance_id))
        if not session:
            return redirect(url_for('autoconfig_pending'), code=302)
        return render_template('autoconfig_logs.html',
                               subtab="autoconf_dev",
                               responsive=str(self._args.madmin_noresponsive).lower(),
                               session_id=session_id
                               )

    @auth_required
    def autoconf_logs_get(self, session_id):
        sql = "SELECT *\n"\
              "FROM `autoconfig_registration`\n"\
              "WHERE `session_id` = %s AND `instance_id` = %s"
        session = self._db.autofetch_row(sql, (session_id, self._db.instance_id))
        if not session:
            return Response('', status=302)
        sql = "SELECT UNIX_TIMESTAMP(`log_time`) as 'log_time', `level`, `msg`\n"\
              "FROM `autoconfig_logs`\n"\
              "WHERE `instance_id` = %s AND `session_id` = %s\n"\
              "ORDER BY `log_time` ASC"
        logs = self._db.autofetch_all(sql, (self._db.instance_id, session_id))
        return jsonify(logs)

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
        sql = "SELECT count(*)\n"\
              "FROM `settings_pogoauth` ag\n"\
              "LEFT JOIN `settings_device` sd ON sd.`account_id` = ag.`account_id`\n"\
              "WHERE ag.`instance_id` = %s AND sd.`device_id` IS NULL"
        ac_issues = AutoConfIssueGenerator(self._db, self._data_manager, self._args, self._storage_obj)
        issues_warning, issues_critical = ac_issues.get_issues()
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
            elif row['status'] == 2:
                row['status_hr'] = 'In-Progress with errors'
            elif row['status'] == 3:
                row['status_hr'] = 'Completed with errors'
            else:
                row['status_hr'] = 'Rejected'
            pending[row['session_id']] = row
        return render_template('autoconfig_pending.html',
                               subtab="autoconf_dev",
                               pending=pending,
                               issues_warning=issues_warning,
                               issues_critical=issues_critical
                               )

    @auth_required
    def autoconfig_pending_dev(self, session_id):
        sql = "SELECT *\n"\
              "FROM `autoconfig_registration`\n"\
              "WHERE `session_id` = %s AND `instance_id` = %s"
        session = self._db.autofetch_row(sql, (session_id, self._db.instance_id))
        if not session:
            return redirect(url_for('autoconfig_pending'), code=302)
        sql = "SELECT ag.`account_id`, ag.`username`\n"\
              "FROM `settings_pogoauth` ag\n"\
              "LEFT JOIN `settings_device` sd ON sd.`device_id` = ag.`device_id`\n"\
              "WHERE ag.`instance_id` = %s AND (sd.`device_id` IS NULL OR sd.`device_id` = %s)"
        ac_issues = AutoConfIssueGenerator(self._db, self._data_manager, self._args, self._storage_obj)
        _, issues_critical = ac_issues.get_issues()
        if issues_critical:
            redirect(url_for('autoconfig_pending'), code=302)
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
