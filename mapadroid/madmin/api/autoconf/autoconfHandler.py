from flask import Response
from .. import apiHandler
from mapadroid.madmin.functions import auth_required


class AutoConfHandler(apiHandler.APIHandler):
    component = None
    iterable = True
    default_sort = None
    has_rpc_calls = False

    def create_routes(self):
        """ Creates all pertinent routes to for the API resource """
        self._app.route('/api/autoconf',
                        methods=['GET'],
                        endpoint='api_autoconf')(self.entrypoint)
        self._app.route('/api/autoconf/<string:session_id>',
                        methods=['GET', 'POST', 'DELETE'],
                        endpoint='api_autoconf_status')(self.entrypoint)
        self._app.route('/api/autoconf/rgc',
                        methods=['POST', 'DELETE', 'GET', 'PATCH'],
                        endpoint='api_autoconf_rgc')(self.entrypoint)
        self._app.route('/api/autoconf/pd',
                        methods=['POST', 'DELETE', 'GET', 'PATCH'],
                        endpoint='api_autoconf_pd')(self.entrypoint)

    # =====================================
    # ========= API Functionality =========
    # =====================================
    @auth_required
    def process_request(self, *args, **kwargs):
        """ Processes an API request
        Returns:
            Flask.Response
        """
        # Begin processing the _request
        session_id = kwargs.get('session_id', None)
        if self.api_req._request.endpoint == 'api_autoconf':
            if self.api_req._request.method == 'GET':
                return self.autoconf_status()
        elif self.api_req._request.endpoint == 'api_autoconf_status':
            if self.api_req._request.method == 'GET':
                return self.autoconf_status(session_id=session_id)
            elif self.api_req._request.method == 'POST':
                return self.autoconf_set_status(session_id)
            elif self.api_req._request.method == 'DELETE':
                return self.autoconf_delete_session(session_id)
        elif self.api_req._request.endpoint == 'api_autoconf_rgc':
            if self.api_req._request.method in ['POST', 'PATCH']:
                return self.autoconf_config_rgc()
            elif self.api_req._request.method == 'DELETE':
                return self.autoconf_delete_rgc()
            elif self.api_req._request.method == 'GET':
                return self.get_config('rgc')
        elif self.api_req._request.endpoint == 'api_autoconf_pd':
            if self.api_req._request.method in ['POST', 'PATCH']:
                return self.autoconf_config_pd()
            elif self.api_req._request.method == 'DELETE':
                return self.autoconf_delete_pd()
            elif self.api_req._request.method == 'GET':
                return self.get_config('pd')
        else:
            return Response(status=404)
