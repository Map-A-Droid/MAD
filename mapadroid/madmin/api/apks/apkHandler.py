import flask

from mapadroid.utils import global_variables, apk_util
from .. import apiHandler


class APKHandler(apiHandler.APIHandler):
    component = None
    iterable = True
    default_sort = None
    has_rpc_calls = False

    def create_routes(self):
        """ Creates all pertinent routes to for the API resource """
        self._app.route('/api/mad_apk',
                        methods=['GET', 'POST'],
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
                if apk_type is not None:
                    apk_type = int(apk_type)
            except:
                apk_type, _ = apk_util.convert_to_backend(apk_type=apk_type)
                if apk_type is None:
                    return (None, 404)
            try:
                apk_arch = kwargs.get('apk_arch', None)
                if apk_arch is not None:
                    apk_arch = int(apk_arch)
            except:
                _, apk_arch = apk_util.convert_to_backend(apk_arch=apk_arch)
            if flask.request.method == 'GET':
                return self.get(apk_type=apk_type, apk_arch=apk_arch)
            elif flask.request.method == 'DELETE':
                return self.delete(apk_type=apk_type, apk_arch=apk_arch)
            elif flask.request.method == 'POST':
                data = self.post(apk_type=apk_type, apk_arch=apk_arch)
                return data
        except:
            return (None, 404)
