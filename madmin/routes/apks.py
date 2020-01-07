from flask import (send_from_directory, render_template, request, jsonify, redirect, url_for, flash, Response)
from madmin.functions import (auth_required, get_quest_areas)
from utils.functions import (generate_path)
from utils.MappingManager import MappingManager
from utils.logging import logger
from utils import apk_util
from utils import global_variables
import json

class apk_manager(object):
    def __init__(self, db, args, app, mapping_manager: MappingManager, deviceUpdater):
        self._db = db
        self._args = args
        self._app = app
        self._mapping_manager = mapping_manager
        self._deviceUpdater = deviceUpdater
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
        return '.' in filename and filename.rsplit('.', 1)[1].lower() in global_variables.MAD_APK_ALLOWED_EXTENSIONS

    def apk_update_status(self):
        update_info = {}
        sql = "SELECT `usage`, `arch`, `version`, `download_status`, `last_checked`\n"\
              "FROM `mad_apk_autosearch`"
        autosearch_data = self._db.autofetch_all(sql)
        for row in autosearch_data:
            composite_key = '%s_%s' % (row['usage'], row['arch'])
            update_info[composite_key] = {}
            sql = "SELECT ma.`version`, fm.`size`\n"\
                  "FROM `mad_apks` ma\n"\
                  "INNER JOIN `filestore_meta` fm ON fm.`filestore_id` = ma.`filestore_id`\n"\
                  "WHERE ma.`usage` = %s AND ma.`arch` = %s"
            curr_info = self._db.autofetch_row(sql, args=(row['usage'], row['arch']))
            if row['download_status'] != 0:
                update_info[composite_key]['download_status'] = row['download_status']
            if row['usage'] == global_variables.MAD_APK_USAGE_POGO:
                if not curr_info or apk_util.is_newer_version(row['version'], curr_info['version']):
                    update_info[composite_key]['update'] = 1
            else:
                if not curr_info or int(curr_info['size']) != int(row['version']):
                    update_info[composite_key]['update'] = 1
            if not update_info[composite_key]:
                del update_info[composite_key]
        return Response(json.dumps(update_info), mimetype='application/json')
    
    @auth_required
    def mad_apks(self):
        apks = apk_util.get_mad_apks(self._db)
        return render_template('madmin_apk_root.html', apks=apks)

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
                if apk_upload and self.allowed_file(apk_upload.filename):
                    apk_type = global_variables.MAD_APK_USAGE[request.form['apk_type']]
                    apk_arch = global_variables.MAD_APK_ARCH[request.form['apk_arch']]
                    apk_util.MADAPKImporter(self._db, apk_upload.filename, apk_upload, apk_upload.content_type,
                                            apk_type = apk_type, architecture = apk_arch, mad_apk = True)
                    return redirect(url_for('mad_apks'))
            except:
                logger.exception('Unhandled exception occurred with the MAD APK', exc_info=True)
        return redirect(url_for('mad_apks'))