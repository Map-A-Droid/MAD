import flask
from .. import apiHandler
from madmin.functions import auth_required

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
        apks = ['pogo', 'rgc', 'pogodroid']
        self._app.route('/api/mad_apk/<string:apk_type>',
                        methods=['GET'],
                        endpoint='api_madapk_apk_type')(self.entrypoint)
        self._app.route('/api/mad_apk/<string:apk_type>/<string:apk_arch>',
                        methods=['GET', 'POST', 'DELETE', 'PUT'],
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
    @auth_required
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
            apk_type = kwargs.get('apk_type', None)
            apk_arch = kwargs.get('apk_arch', None)
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