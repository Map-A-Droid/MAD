import json
import logging
import math
import sys
import time

from flask import (Flask, request, Response)

from utils.authHelper import check_auth

app = Flask(__name__)
log = logging.getLogger(__name__)
allowed_origins = None
auths = None
application_args = None


class EndpointAction(object):

    def __init__(self, action):
        self.action = action
        self.response = Response(status=200, headers={})

    def __call__(self, *args):
        global allowed_origins, application_args, auths
        origin = request.headers.get('Origin')
        abort = False
        if not origin:
            log.warning("Missing Origin header in request")
            self.response = Response(status=500, headers={})
            abort = True
        elif allowed_origins is not None and (origin is None or origin not in allowed_origins):
            self.response = Response(status=403, headers={})
            abort = True
        elif auths is not None: # TODO check auth properly...
            auth = request.headers.get('Authorization', None)
            if auth is None or not check_auth(auth, application_args, auths):
                log.warning("Unauthorized attempt to POST from %s" % str(request.remote_addr))
                self.response = Response(status=403, headers={})
                abort = True
        if not abort:
            try:
                # TODO: use response data
                if len(request.data) > 0:
                    request_data = json.loads(request.data)
                else:
                    request_data = {}
                response_payload = self.action(origin, request_data)
                if response_payload is None:
                    response_payload = ""
                self.response.data = response_payload
            except Exception as e: # TODO: catch exact exception
                log.warning("Could not get JSON data from request: %s" % str(e))
                self.response = Response(status=500, headers={})
        return self.response


class MITMReceiver(object):
    def __init__(self, listen_ip, listen_port, mitm_mapper, args_passed, auths_passed):
        global application_args, auths
        application_args = args_passed
        auths = auths_passed
        self.__listen_ip = listen_ip
        self.__listen_port = listen_port
        self.__mitm_mapper = mitm_mapper
        self.app = Flask("MITMReceiver")
        self.add_endpoint(endpoint='/', endpoint_name='receive_protos', handler=self.proto_endpoint,
                          methods_passed=['POST'])
        self.add_endpoint(endpoint='/get_latest_mitm', endpoint_name='get_latest_mitm', handler=self.get_latest,
                          methods_passed=['GET'])

    def run_receiver(self):
        self.app.run(host=self.__listen_ip, port=int(self.__listen_port), threaded=True, use_reloader=False)

    def add_endpoint(self, endpoint=None, endpoint_name=None, handler=None, options=None, methods_passed=None):
        if methods_passed is None:
            log.fatal("Invalid REST method specified")
            sys.exit(1)
        self.app.add_url_rule(endpoint, endpoint_name, EndpointAction(handler), methods=methods_passed)

    def proto_endpoint(self, origin, data):
        # data = json.loads(request.data)
        type = data.get("type", None)
        if type is None:
            log.warning("Could not read method ID. Stopping processing of proto")
            return None
        self.__mitm_mapper.update_latest(origin, timestamp=int(math.floor(time.time())), key=type, values_dict=data)
        return None

    def get_latest(self, origin, data):
        injected_settings = self.__mitm_mapper.request_latest(origin, "injected_settings")
        # TODO: replace with encounter IDs at some point...
        mon_ids_iv = self.__mitm_mapper.request_latest(origin, "mon_ids_iv")
        if mon_ids_iv is not None:
            mon_ids_iv = mon_ids_iv.get("values", None)
        response = {"mon_ids_iv": mon_ids_iv, "injected_settings": injected_settings}
        return json.dumps(response)
