import flask
from .. import apiHandler
from utils import global_variables

class APKHandler(apiHandler.APIHandler):
    component = None
    iterable = True
    default_sort = None
    has_rpc_calls = False

    def create_routes(self):
        """ Creates all pertinent routes to for the API resource """
        self._app.route('/api/mad_apk',
                        methods=['GET'],
                        endpoint='api_madapk')(self.entrypoint)
        self._app.route('/api/mad_apk/<string:apk_type>',
                        methods=['GET'],
                        endpoint='api_madapk_apk_type')(self.entrypoint)
        self._app.route('/api/mad_apk/<string:apk_type>/<string:apk_arch>',
                        methods=['GET', 'POST', 'DELETE'],
                        endpoint='api_madapk_apk_type_arch')(self.entrypoint)
        self._app.route('/api/mad_apk/<string:apk_type>/<string:apk_arch>/download',
                        methods=['GET'],
                        endpoint='api_madapk_apk_download_arch')(self.entrypoint)
        self._app.route('/api/mad_apk/<string:apk_type>/download',
                        methods=['GET'],
                        endpoint='api_madapk_apk_download_noarch')(self.entrypoint)

    # =====================================
    # ========= API Functionality =========
    # =====================================
    def process_request(self, *args, **kwargs):
        """ Processes an API request
        Args:
            endpoint(str): Useless identifier to allow Flask to use a generic function signature
            identifier(str): Identifier for the object to interact with
        Returns:
            Flask.Response
        """
        # Begin processing the request
        try:
            try:
                apk_type = kwargs.get('apk_type', None)
                apk_type = int(apk_type)
            except:
                pass
            try:
                apk_arch = kwargs.get('apk_arch', None)
                apk_arch = int(apk_arch)
            except:
                pass
                #apk_arch = global_variables.MAD_APK_ARCH_NOARCH
            if apk_type and isinstance(apk_type, str):
                if apk_type == 'pogo':
                    apk_type = global_variables.MAD_APK_USAGE_POGO
                elif apk_type == 'rgc':
                    apk_type = global_variables.MAD_APK_USAGE_RGC
                elif apk_type == 'pogodroid':
                    apk_type = global_variables.MAD_APK_USAGE_PD
                else:
                    return (None, 404)
            if apk_arch and isinstance(apk_arch, str):
                if apk_arch == 'armeabi-v7a':
                    apk_arch = global_variables.MAD_APK_ARCH_ARMEABI_V7A
                elif apk_arch == 'arm64-v8a':
                    apk_arch = global_variables.MAD_APK_ARCH_ARM64_V8A
                elif apk_arch == 'noarch':
                    apk_arch = global_variables.MAD_APK_ARCH_NOARCH
                else:
                    global_variables.MAD_APK_ARCH_NOARCH
            if flask.request.method == 'GET':
                return self.get(apk_type=apk_type, apk_arch=apk_arch)
            elif flask.request.method == 'DELETE':
                return self.delete(apk_type=apk_type, apk_arch=apk_arch)
            elif flask.request.method == 'POST':
                data = self.post(apk_type=apk_type, apk_arch=apk_arch)
                return data
        except:
            import traceback
            traceback.print_exc()
            return (None, 404) 