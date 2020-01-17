# TODO - Move POST / PUT from routes/apk to here
from threading import Thread

import flask

from mapadroid.madmin.functions import auth_required
from mapadroid.utils import global_variables
from mapadroid.utils.authHelper import check_auth
from mapadroid.utils.apk_util import (
    chunk_generator, 
    AutoDownloader,
    get_mad_apks
)
from .apkHandler import APKHandler


class APIMadAPK(APKHandler):
    component = 'mad_apk'
    default_sort = None
    description = 'GET/Delete MAD APKs'
    uri_base = 'mad_apk'

    def allowed_file(self, filename):
        return '.' in filename and filename.rsplit('.', 1)[
            1].lower() in global_variables.MAD_APK_ALLOWED_EXTENSIONS

    def get_apk_list(self, apk_type, apk_arch):
        apks = get_mad_apks(self.dbc)
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
                auths = self._mapping_manager.get_auths()
                authBase64 = self.api_req.headers['Authorization']
                if auths and authBase64 and not check_auth(authBase64, None, auths):
                    return flask.make_response('Please login with a valid origin and auth', 401)
            except KeyError:
                return flask.make_response('Please login with a valid origin and auth', 401)
            try:
                if (apks[1]) == 200:
                    mad_apk = apks[0]
                    return flask.Response(
                        flask.stream_with_context(chunk_generator(self.dbc, mad_apk['file_id'])),
                        content_type=mad_apk['mimetype'],
                        headers={
                            'Content-Disposition': f'attachment; filename=%s' % (mad_apk['filename'])
                        }
                    )
                else:
                    return apks
            except (KeyError, TypeError):
                return (None, 404)
            return apks
        else:
            return apks

    @auth_required
    def post(self, apk_type, apk_arch):
        try:
            call = self.api_req.data['call']
            args = self.api_req.data.get('args', {})
            if call == 'import':
                downloader = AutoDownloader(self.dbc)
                try:
                    args = (int(apk_type), int(apk_arch))
                    t = Thread(target=downloader.apk_download, args=args)
                    t.start()
                    return (None, 204)
                except TypeError:
                    return (None, 404)
            elif call == 'search':
                downloader = AutoDownloader(self.dbc)
                try:
                    downloader.apk_search(int(apk_type), int(apk_arch))
                    return (None, 204)
                except TypeError:
                    return (None, 404)
            elif call == 'search_download':
                downloader = AutoDownloader(self.dbc)
                try:
                    downloader.apk_all_actions()
                    return (None, 204)
                except TypeError:
                    return (None, 404)
            else:
                # RPC not implemented
                return (call, 501)
        except KeyError:
            import traceback
            traceback.print_exc()
            return (call, 501)
        return (None, 500)

    @auth_required
    def delete(self, apk_type, apk_arch):
        if apk_type is None:
            return (None, 404)
        try:
            file_data = self.get(apk_type, apk_arch)[0]
            del_data = {
                'filestore_id': file_data['file_id']
            }
            self.dbc.autoexec_delete('filestore_meta', del_data)
            return (None, 202)
        except KeyError:
            return (None, 404)
