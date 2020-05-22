from apkutils.apkfile import BadZipFile, LargeZipFile
import flask
import json
import io
from threading import Thread
from .apkHandler import APKHandler
from mapadroid.mad_apk import APK_Arch, APK_Type, stream_package, lookup_package_info, APKWizard,\
    supported_pogo_version, get_apk_status, MAD_APKS, PackageImporter, InvalidVersion
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
            if apk_type is None and apk_arch is APK_Arch.noarch:
                return (get_apk_status(self.storage_obj), 200)
            else:
                return lookup_package_info(self.storage_obj, apk_type, apk_arch)

    @auth_required
    def post(self, apk_type: APK_Type, apk_arch: APK_Arch):
        is_upload: bool = False
        apk: io.BytesIO = None
        version: str = None
        filename: str = None
        if 'multipart/form-data' in self.api_req.content_type:
            filename = self.api_req.data['data'].get('filename', None)
            try:
                apk = io.BytesIO(self.api_req.data['files'].get('file').read())
            except AttributeError:
                return ('No file present', 406)
            is_upload = True
        if self.api_req.content_type == 'application/octet-stream':
            filename = self.api_req.headers.get('filename', None)
            apk = io.BytesIO(self.api_req.data)
            is_upload = True
        if is_upload:
            if filename is None:
                return ('filename must be specified', 406)
            elems: MAD_APKS = get_apk_status(self.storage_obj)
            try:
                elems[apk_type][apk_arch]
            except KeyError:
                return ('Non-supported Type / Architecture', 406)
            filename_split = filename.rsplit('.', 1)
            if filename_split[1] == 'zip':
                mimetype = 'application/zip'
                try:
                    version = filename_split[0].split('_')[1]
                except IndexError:
                    return ('ZIP must be uploaded as <name>_<version>.zip', 406)
            elif filename_split[1] == 'apk':
                mimetype = 'application/vnd.android.package-archive'
            else:
                return ('Unsupported extension', 406)
            try:
                PackageImporter(apk_type, apk_arch, self.storage_obj, apk, mimetype, version=version)
                if 'multipart/form-data' in self.api_req.content_type:
                    return flask.redirect(None, code=201)
                return (None, 201)
            except (BadZipFile, LargeZipFile) as err:
                return (str(err), 406)
            except Exception:
                self._logger.opt(exception=True).critical("An unhanded exception occurred!")
                return (None, 500)
        else:
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
