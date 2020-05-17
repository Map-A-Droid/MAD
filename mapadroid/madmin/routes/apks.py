from flask import (render_template, request, redirect, url_for, flash, Response)
import io
import json
import werkzeug.exceptions
from mapadroid.mad_apk import AbstractAPKStorage, get_apk_status, PackageImporter, parse_frontend, is_newer_version
from mapadroid.madmin.functions import auth_required
from mapadroid.utils import MappingManager
from mapadroid.utils import global_variables
from mapadroid.utils.logging import logger


class apk_manager(object):
    def __init__(self, db, args, app, mapping_manager: MappingManager, deviceUpdater, storage_obj: AbstractAPKStorage):
        self._db = db
        self._args = args
        self._app = app
        self._mapping_manager = mapping_manager
        self._deviceUpdater = deviceUpdater
        self.storage_obj = storage_obj
        self.add_route()

    def add_route(self):
        routes = [
            ("/apk", self.mad_apks),
            ("/apk_upload", self.upload_file, ['POST']),
            ("/apk_update_status", self.apk_update_status),
        ]
        for route_def in routes:
            if len(route_def) == 2:
                route, view_func = route_def
                self._app.route(route)(view_func)
            elif len(route_def) == 3:
                route, view_func, methods = route_def
                self._app.route(route, methods=methods)(view_func)

    def allowed_file(self, filename):
        return '.' in filename and filename.rsplit('.', 1)[
            1].lower() in global_variables.MAD_APK_ALLOWED_EXTENSIONS

    def apk_update_status(self):
        update_info = {}
        sql = "SELECT `usage`, `arch`, `version`, `download_status`, `last_checked`\n" \
              "FROM `mad_apk_autosearch`"
        autosearch_data = self._db.autofetch_all(sql)
        apk_info = get_apk_status(self.storage_obj)
        for row in autosearch_data:
            composite_key = '%s_%s' % (row['usage'], row['arch'])
            update_info[composite_key] = {}
            if row['download_status'] != 0:
                update_info[composite_key]['download_status'] = row['download_status']
            try:
                curr_info = apk_info[str(row['usage'])][str(row['arch'])]
            except KeyError:
                curr_info = None
            if row['usage'] == global_variables.MAD_APK_USAGE_POGO:
                if not curr_info or is_newer_version(row['version'], curr_info['version']):
                    update_info[composite_key]['update'] = 1
            else:
                if curr_info is None or int(curr_info['size']) != int(row['version']):
                    update_info[composite_key]['update'] = 1
            if not update_info[composite_key]:
                del update_info[composite_key]
        return Response(json.dumps(update_info), mimetype='application/json')

    @auth_required
    def mad_apks(self):
        return render_template('madmin_apk_root.html', apks=get_apk_status(self.storage_obj))

    @auth_required
    def upload_file(self):
        if request.method == 'POST':
            try:
                if len(request.files) == 0:
                    flash('No selected file')
                    return redirect(url_for('mad_apks'))
                apk_upload = request.files['apk']
                if apk_upload.filename == '':
                    flash('No selected file')
                    return redirect(url_for('mad_apks'))
                if not self.allowed_file(apk_upload.filename):
                    flash('File extension not allowed')
                    return redirect(url_for('mad_apks'))
                if apk_upload:
                    parsed = parse_frontend(**request.form)
                    if type(parsed) == Response:
                        return parsed
                    apk_type, apk_arch = parsed
                    mimetype = 'application/zip'
                    if apk_upload.filename.rsplit('.', 1)[1] == 'apk':
                        mimetype = 'application/vnd.android.package-archive'
                    # TODO - Probably a better way to handle this.  However it does not like the incoming type,
                    # io.BufferedRandom
                    apk = io.BytesIO(apk_upload.stream.read())
                    PackageImporter(apk_type, apk_arch, self.storage_obj, apk, mimetype)
                    return redirect(url_for('mad_apks'))
            except werkzeug.exceptions.RequestEntityTooLarge:
                flash('File too large.  Please use a a smaller file')
                return redirect(url_for('mad_apks'))
            except:
                logger.exception('Unhanded exception occurred with the MAD APK', exc_info=True)
        return redirect(url_for('mad_apks'))
