# TODO - Move POST / PUT from routes/apk to here
from .apkHandler import APKHandler
import utils.apk_util
import flask
import io
from utils import global_variables
import tempfile
import apkutils
from utils.logging import logger

class APIMadAPK(APKHandler):
    component = 'mad_apk'
    default_sort = None
    description = 'GET/Delete MAD APKs'
    uri_base = 'mad_apk'

    def allowed_file(self, filename):
        return '.' in filename and filename.rsplit('.', 1)[1].lower() in global_variables.MAD_APK_ALLOWED_EXTENSIONS

    def get_apk_list(self, apk_type, apk_arch):
        apks = utils.apk_util.get_mad_apks(self.dbc)
        try:
            apks[apk_type]
            try:
                if apks[apk_type][apk_arch]['version'] != None:
                    return (apks[apk_type][apk_arch], 200)
                else:
                    return ('MAD APK for %s has not been uploaded' % (apk_type,), 404)
            except:
                if apk_arch:
                    return ('Invalid arch_type.  Valid arch_types: %s' % apks[apk_type].keys(), 404)
                elif len(apks[apk_type]) == 1:
                    key = list(apks[apk_type].keys())[0]
                    if apks[apk_type][key]['version'] != None:
                        return (apks[apk_type][key], 200)
                    return ('MAD APK for %s has not been uploaded' % (apk_type,), 404)
                else:
                    return (apks[apk_type], 200)
        except:
            if apk_type:
                return ('Invalid apk_type.  Valid apk_types: %s' % apks.keys(), 404)
            else:
                return (apks, 200)

    def get(self, apk_type, apk_arch):
        apks = self.get_apk_list(apk_type, apk_arch)
        if flask.request.url.split('/')[-1] == 'download':
            try:
                if(apks[1]) == 200:
                    file_id = apks[0]['file_id']
                    sql = 'SELECT * FROM `filestore` WHERE `id` = %s'
                    db_data = self.dbc.autofetch_row(sql, args=(file_id,))
                    data = io.BytesIO(db_data['data'])
                    data.seek(0,0)
                    return flask.send_file(data, as_attachment=True, attachment_filename=db_data['filename'])
                else:
                    return apks
            except (KeyError, TypeError):
                return (None, 404)
            return apks
        else:
            return apks

    def post(self, apk_type, apk_arch):
        return (None, 500)

    def delete(self, apk_type, apk_arch):
        if apk_type is None:
            return (None, 404)
        try:
            file_data = self.get(apk_type, apk_arch)[0]
            del_data = {
                'id': file_data['file_id']
            }
            self.dbc.autoexec_delete('filestore', del_data)
            return (None, 202)
        except KeyError:
            return (None, 404)
