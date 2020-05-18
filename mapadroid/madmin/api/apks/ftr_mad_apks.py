import flask
import json
from threading import Thread
from .apkHandler import APKHandler
from mapadroid.mad_apk import APK_Arch, APK_Type, stream_package, lookup_package_info, APKWizard, supported_pogo_version
from mapadroid.madmin.functions import auth_required
from mapadroid.utils import global_variables
from mapadroid.utils.authHelper import check_auth



class APIMadAPK(APKHandler):
    component = 'mad_apk'
    default_sort = None
    description = 'GET/Delete MAD APKs'
    uri_base = 'mad_apk'

    def allowed_file(self, filename):
        return '.' in filename and filename.rsplit('.', 1)[
            1].lower() in global_variables.MAD_APK_ALLOWED_EXTENSIONS

    @auth_required
    def get(self, apk_type: APK_Type, apk_arch: APK_Arch):
        if flask.request.url.split('/')[-1] == 'download':
            return stream_package(self.dbc, self.storage_obj, apk_type, apk_arch)
        else:
            (package_info, status_code) = lookup_package_info(self.storage_obj, apk_type, apk_arch)
            return flask.Response(status=status_code, response=json.dumps(package_info))

    @auth_required
    def post(self, apk_type: APK_Type, apk_arch: APK_Arch):
        try:
            call = self.api_req.data['call']
            args = self.api_req.data.get('args', {})
            wizard = APKWizard(self.dbc, self.storage_obj)
            if call == 'import':
                thread_args = (apk_type, apk_arch)
                t = Thread(target=wizard.apk_download, args=thread_args)
                t.start()
                return (None, 204)
            elif call == 'search':
                wizard.apk_search(apk_type, apk_arch)
                return (None, 204)
            elif call == 'search_download':
                try:
                    wizard.apk_all_actions()
                    return (None, 204)
                except TypeError:
                    return (None, 404)
            else:
                return (call, 501)
        except KeyError:
            import traceback
            traceback.print_exc()
            return (call, 501)

        return (None, 500)


    @auth_required
    def delete(self, apk_type: APK_Type, apk_arch: APK_Arch):
        if apk_type is None:
            return (None, 404)
        resp = self.storage_obj.delete_file(apk_type, apk_arch)
        if type(resp) == flask.Response:
            return resp
        if resp:
            return (None, 202)
        return (None, 404)
        # # try:
        # #     file_data = self.get(apk_type, apk_arch)[0]
        # #     del_data = {
        # #         'filestore_id': file_data['file_id']
        # #     }
        # #     self.dbc.autoexec_delete('filestore_meta', del_data)
        # #     return (None, 202)
        # except KeyError:
        #     return (None, 404)
