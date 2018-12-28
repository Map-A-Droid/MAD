import json
import logging
import math
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
                self.action(origin, json.loads(request.data))
            except Exception as e: # TODO: catch exact exception
                log.warning("Could not get JSON data from request: %s" % str(e))
                self.response = Response(status=500, headers={})
        return self.response


class MITMReceiver(object):
    def __init__(self, listen_ip, listen_port, received_mapping, args_passed, auths_passed):
        global application_args, auths
        application_args = args_passed
        auths = auths_passed
        self.__listen_ip = listen_ip
        self.__listen_port = listen_port
        self.__received_mapping = received_mapping
        self.app = Flask("MITMReceiver")
        self.add_endpoint(endpoint='/', endpoint_name='receive_protos', handler=self.proto_endpoint)

    def run_receiver(self):
        self.app.run(host=self.__listen_ip, port=int(self.__listen_port), threaded=True, use_reloader=False)

    def add_endpoint(self, endpoint=None, endpoint_name=None, handler=None, options=None):
        methods_passed = ['POST']
        self.app.add_url_rule(endpoint, endpoint_name, EndpointAction(handler), methods=methods_passed)

    def proto_endpoint(self, origin, data):
        # data = json.loads(request.data)
        type = data.get("type", None)
        if type is None:
            log.warning("Could not read method ID. Stopping processing of proto")
            return
        self.__received_mapping.update_retrieved(origin, type, data, int(math.floor(time.time())))
