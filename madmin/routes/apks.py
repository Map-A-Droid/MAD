from flask import (send_from_directory, render_template, request, jsonify, redirect, url_for, flash)
from madmin.functions import (auth_required, get_quest_areas)
from utils.functions import (generate_path)
from utils.MappingManager import MappingManager
from utils.logging import logger
import utils.apk_util
from werkzeug.utils import secure_filename
from utils import global_variables
import apkutils
import os
import tempfile

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
    
    @auth_required
    def mad_apks(self):
        apks = utils.apk_util.get_mad_apks(self._db)
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
                    filename = secure_filename(apk_upload.filename)
                    filepath = os.path.join(tempfile.gettempdir(), filename)
                    apk_type = global_variables.MAD_APK_USAGE[request.form['apk_type']]
                    apk_arch = global_variables.MAD_APK_ARCH[request.form['apk_arch']]
                    # Temporarily save the file so we can do our version processing
                    try:
                        apk_upload.save(filepath)
                        apk = apkutils.APK(filepath)
                        version = apk.get_manifest()['@android:versionName']
                        apk_upload.seek(0,0)
                        data = apk_upload.read()
                        logger.info('New APK uploaded for {} {} [{}]', request.form['apk_type'],
                                                                       request.form['apk_arch'],
                                                                       version)
                        apk_upload.seek(0,0)
                        # Determine if we already have this file-type uploaded.  If so, remove it once the new one is
                        # completed and update the id
                        filestore_id_sql = "SELECT `id` FROM `mad_apks` WHERE `usage` = %s AND `arch` = %s"
                        filestore_id = self._db.autofetch_value(filestore_id_sql, args=(apk_type, apk_arch,))
                        if filestore_id:
                            delete_data = {
                                'id': filestore_id
                            }
                            self._db.autoexec_delete('filestore', delete_data)
                        insert_data = {
                            'filename': filename,
                            'data': apk_upload.read()
                        }
                        new_id = self._db.autoexec_insert('filestore', insert_data)
                        insert_data = {
                            'id': new_id,
                            'usage': apk_type,
                            'arch': apk_arch,
                            'version': version,
                        }
                        self._db.autoexec_insert('mad_apks', insert_data)
                    except Exception as err:
                        logger.exception('Unable to save the apk', exc_info=True)
                    finally:
                        try:
                            os.unlink(filepath)
                        except:
                            pass
                    return redirect(url_for('mad_apks'))
            except:
                import traceback
                traceback.print_exc()
        return redirect(url_for('mad_apks'))