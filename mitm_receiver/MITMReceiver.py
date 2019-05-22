import json
import math
import sys

import time
from multiprocessing import JoinableQueue, Process
from multiprocessing.managers import BaseManager

from flask import Flask, Response, request
from gevent.pywsgi import WSGIServer

from db.DbFactory import DbFactory
from mitm_receiver.MITMDataProcessor import MitmDataProcessor
from mitm_receiver.MitmMapper import MitmMapper
from utils.authHelper import check_auth
from utils.logging import LogLevelChanger, logger

app = Flask(__name__)
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
            logger.warning("Missing Origin header in request")
            self.response = Response(status=500, headers={})
            abort = True
        elif allowed_origins is not None and (origin is None or origin not in allowed_origins):
            self.response = Response(status=403, headers={})
            abort = True
        elif auths is not None:  # TODO check auth properly...
            auth = request.headers.get('Authorization', None)
            if auth is None or not check_auth(auth, application_args, auths):
                logger.warning(
                    "Unauthorized attempt to POST from {}", str(request.remote_addr))
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
                self.response = Response(status=200, headers={})
                self.response.data = response_payload
            except Exception as e:  # TODO: catch exact exception
                logger.warning(
                    "Could not get JSON data from request: {}", str(e))
                self.response = Response(status=500, headers={})
        return self.response


class MITMReceiver(Process):
    def __init__(self, listen_ip, listen_port, mitm_mapper, args_passed, auths_passed, db_wrapper, name=None):
        global application_args, auths
        Process.__init__(self, name=name)
        application_args = args_passed
        auths = auths_passed
        self.__listen_ip = listen_ip
        self.__listen_port = listen_port
        self.__mitm_mapper: MitmMapper = mitm_mapper
        self.app = Flask("MITMReceiver")
        self.add_endpoint(endpoint='/', endpoint_name='receive_protos', handler=self.proto_endpoint,
                          methods_passed=['POST'])
        self.add_endpoint(endpoint='/get_latest_mitm/', endpoint_name='get_latest_mitm/', handler=self.get_latest,
                          methods_passed=['GET'])
        self.add_endpoint(endpoint='/get_addresses/', endpoint_name='get_addresses/', handler=self.get_addresses,
                          methods_passed=['GET'])
        self._data_queue: JoinableQueue = JoinableQueue()
        self._db_wrapper = db_wrapper
        self.worker_threads = []
        for i in range(application_args.mitmreceiver_data_workers):
            data_processor: MitmDataProcessor = MitmDataProcessor(self._data_queue, application_args,
                                                                  self.__mitm_mapper, db_wrapper,
                                                                  name='MITMReceiver-%s' % str(i))
            data_processor.start()
            self.worker_threads.append(data_processor)

    def shutdown(self):
        logger.info("MITMReceiver stop called...")
        self._data_queue.join()
        logger.info("Adding None to queue")
        for i in range(application_args.mitmreceiver_data_workers):
            self._data_queue.put(None)
        logger.info("Trying to join workers...")
        for t in self.worker_threads:
            t.join()
        logger.info("Workers stopped...")

    def run(self):
        httpsrv = WSGIServer((self.__listen_ip, int(
            self.__listen_port)), self.app.wsgi_app, log=LogLevelChanger)
        try:
            httpsrv.serve_forever()
        except KeyboardInterrupt as e:
            httpsrv.close()
            logger.info("Received STOP signal in MITMReceiver")
        finally:
            logger.info("Stopping MITMReceiver")

    def add_endpoint(self, endpoint=None, endpoint_name=None, handler=None, options=None, methods_passed=None):
        if methods_passed is None:
            logger.error("Invalid REST method specified")
            sys.exit(1)
        self.app.add_url_rule(endpoint, endpoint_name,
                              EndpointAction(handler), methods=methods_passed)

    def proto_endpoint(self, origin, data):
        type = data.get("type", None)
        if type is None or type == 0:
            logger.warning(
                "Could not read method ID. Stopping processing of proto")
            return None
        if not self.__mitm_mapper.get_injection_status(origin):
            logger.info("Worker {} is injected now", str(origin))
            self.__mitm_mapper.set_injection_status(origin)
        # extract timestamp from data
        timestamp: float = data.get("timestamp", int(math.floor(time.time())))
        self.__mitm_mapper.update_latest(
            origin, timestamp_received_raw=timestamp, timestamp_received_receiver=time.time(), key=type,
            values_dict=data)
        self._data_queue.put(
            (timestamp, data, origin)
        )
        return None

    def get_latest(self, origin, data):
        injected_settings = self.__mitm_mapper.request_latest(
            origin, "injected_settings")

        ids_iv = self.__mitm_mapper.request_latest(origin, "ids_iv")
        if ids_iv is not None:
            ids_iv = ids_iv.get("values", None)

        ids_encountered = self.__mitm_mapper.request_latest(
            origin, "ids_encountered")
        if ids_encountered is not None:
            ids_encountered = ids_encountered.get("values", None)
        response = {"ids_iv": ids_iv, "injected_settings": injected_settings,
                    "ids_encountered": ids_encountered}
        return json.dumps(response)

    def get_addresses(self, origin, data):
        with open('configs/addresses.json') as f:
            address_object = json.load(f)
        return json.dumps(address_object)
