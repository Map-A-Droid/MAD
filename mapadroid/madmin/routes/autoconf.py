from io import BytesIO
from typing import Optional, List, Tuple

from flask import (Response, jsonify, redirect, render_template, send_file,
                   url_for)

from mapadroid.db.DbWrapper import DbWrapper
from mapadroid.db.helper.AutoconfigLogsHelper import AutoconfigLogHelper
from mapadroid.db.helper.AutoconfigRegistrationHelper import AutoconfigRegistrationHelper
from mapadroid.db.helper.SettingsAuthHelper import SettingsAuthHelper
from mapadroid.db.helper.SettingsDeviceHelper import SettingsDeviceHelper
from mapadroid.db.helper.SettingsPogoauthHelper import SettingsPogoauthHelper
from mapadroid.db.model import SettingsAuth, AutoconfigRegistration, SettingsDevice, SettingsPogoauth, AutoconfigLog
from mapadroid.madmin.functions import auth_required
from mapadroid.utils.autoconfig import (AutoConfIssueGenerator, PDConfig,
                                        RGCConfig)


class AutoConfigManager(object):
    def __init__(self, app, db_wrapper: DbWrapper, args, storage_obj):
        self._db_wrapper = db_wrapper
        self._app = app
        self._args = args
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
    async def autoconfig_download_file(self):
        ac_issues = AutoConfIssueGenerator(self._db_wrapper, self._args, self._storage_obj)
        if ac_issues.has_blockers():
            return Response('Basic requirements not met', status=406, headers=ac_issues.get_headers())
        pd_conf = PDConfig(self._db_wrapper, self._args)
        config_file = BytesIO()
        info = [pd_conf.contents['post_destination']]
        try:
            if pd_conf.contents['mad_auth'] is not None:
                auth: Optional[SettingsAuth] = await SettingsAuthHelper.get(session, instance_id,
                                                                            pd_conf.contents['mad_auth'])
                if auth is not None:
                    info.append(f"{auth.username}:{auth.password}")
        except KeyError:
            # No auth defined for RGC so theres probably no auth for the system
            pass
        config_file.write('\n'.join(info).encode('utf-8'))
        config_file.seek(0, 0)
        return send_file(config_file, as_attachment=True, attachment_filename='mad_autoconf.txt',
                         mimetype='text/plain')

    @auth_required
    async def autoconf_logs(self, session_id):
        sessions: List[AutoconfigRegistration] = await AutoconfigRegistrationHelper\
            .get_all_of_instance(session, instance_id=self._db_wrapper.__instance_id, session_id=session_id)

        if not sessions:
            return redirect(url_for('autoconfig_pending'), code=302)
        return render_template('autoconfig_logs.html',
                               subtab="autoconf_dev",
                               responsive=str(self._args.madmin_noresponsive).lower(),
                               session_id=session_id
                               )

    @auth_required
    async def autoconf_logs_get(self, session_id):
        sessions: List[AutoconfigRegistration] = await AutoconfigRegistrationHelper\
            .get_all_of_instance(session, instance_id=self._db_wrapper.__instance_id, session_id=session_id)
        if not sessions:
            return Response('', status=302)
        logs: List[Tuple[int, int, str]] = await AutoconfigLogHelper.get_transformed(session,
                                                                                     self._db_wrapper.__instance_id)
        return jsonify(logs)

    @auth_required
    async def autoconf_pd(self):
        config = PDConfig(self._db_wrapper, self._args)
        auths: List[SettingsAuth] = await SettingsAuthHelper.get_all(session, self._db_wrapper.__instance_id)
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
        ac_issues = AutoConfIssueGenerator(self._db_wrapper, self._args, self._storage_obj)
        issues_warning, issues_critical = ac_issues.get_issues()
        pending_entries: List[Tuple[AutoconfigRegistration, SettingsDevice]] = \
            await AutoconfigRegistrationHelper.get_pending(session, self._db_wrapper.__instance_id)

        return render_template('autoconfig_pending.html',
                               subtab="autoconf_dev",
                               pending=pending_entries,
                               issues_warning=issues_warning,
                               issues_critical=issues_critical
                               )

    @auth_required
    async def autoconfig_pending_dev(self, session_id):
        sessions: List[AutoconfigRegistration] = await AutoconfigRegistrationHelper\
            .get_all_of_instance(session, instance_id=self._db_wrapper.__instance_id, session_id=session_id)
        if not sessions:
            return redirect(url_for('autoconfig_pending'), code=302)
        ac_issues = AutoConfIssueGenerator(self._db_wrapper, self._args, self._storage_obj)
        _, issues_critical = ac_issues.get_issues()
        if issues_critical:
            redirect(url_for('autoconfig_pending'), code=302)
        registration_session: AutoconfigRegistration = sessions[0]
        pogoauths: List[SettingsPogoauth] = await SettingsPogoauthHelper.get_of_autoconfig(session,
                                                                                           self._db_wrapper.__instance_id,
                                                                                           registration_session.device_id)
        devices: List[SettingsDevice] = await SettingsDeviceHelper.get_all(session, self._db_wrapper.__instance_id)
        uri = "{}/{}".format(url_for('api_autoconf'), session_id)
        redir_uri = url_for('autoconfig_pending')
        return render_template('autoconfig_pending_dev.html',
                               subtab="autoconf_dev",
                               element=registration_session,
                               devices=devices,
                               accounts=pogoauths,
                               uri=uri,
                               redirect=redir_uri,
                               method='POST'
                               )

    @auth_required
    def autoconf_rgc(self):
        config = RGCConfig(self._db_wrapper, self._args)
        auths: List[SettingsAuth] = await SettingsAuthHelper.get_all(session, self._db_wrapper.__instance_id)
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
