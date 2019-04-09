import json
import math
import sys
import threading
import time
from datetime import datetime
from queue import Queue

from flask import (Flask, Response, request)
from loguru import logger
from gevent.pywsgi import WSGIServer

from utils.logging import MadLoggerUtils
from utils.authHelper import check_auth

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
                logger.warning("Unauthorized attempt to POST from {}", str(request.remote_addr))
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
                logger.warning("Could not get JSON data from request: {}", str(e))
                self.response = Response(status=500, headers={})
        return self.response


class MITMReceiver(object):
    def __init__(self, listen_ip, listen_port, mitm_mapper, args_passed, auths_passed, db_wrapper):
        global application_args, auths
        application_args = args_passed
        auths = auths_passed
        self.__listen_ip = listen_ip
        self.__listen_port = listen_port
        self.__mitm_mapper = mitm_mapper
        self.app = Flask("MITMReceiver")
        self.add_endpoint(endpoint='/', endpoint_name='receive_protos', handler=self.proto_endpoint,
                          methods_passed=['POST'])
        self.add_endpoint(endpoint='/get_latest_mitm/', endpoint_name='get_latest_mitm/', handler=self.get_latest,
                          methods_passed=['GET'])
        self._data_queue = Queue()
        self._db_wrapper = db_wrapper
        self.worker_threads = []
        for i in range(application_args.mitmreceiver_data_workers):
            t = threading.Thread(name='MITMReceiver-%s' % str(i),
                                 target=self.received_data_worker)
            t.start()
            self.worker_threads.append(t)

    def stop_receiver(self):
        global application_args
        self._data_queue.join()
        for i in range(application_args.mitmreceiver_data_workers):
            self._data_queue.put(None)
        for t in self.worker_threads:
            t.join()

    def run_receiver(self):
        httpsrv = WSGIServer((self.__listen_ip, int(self.__listen_port)), self.app.wsgi_app, log=MadLoggerUtils)
        httpsrv.serve_forever()

    def add_endpoint(self, endpoint=None, endpoint_name=None, handler=None, options=None, methods_passed=None):
        if methods_passed is None:
            logger.error("Invalid REST method specified")
            sys.exit(1)
        self.app.add_url_rule(endpoint, endpoint_name, EndpointAction(handler), methods=methods_passed)

    def proto_endpoint(self, origin, data):
        type = data.get("type", None)
        if type is None or type == 0:
            logger.warning("Could not read method ID. Stopping processing of proto")
            return None
        timestamp = int(math.floor(time.time()))
        self.__mitm_mapper.update_latest(origin, timestamp=timestamp, key=type, values_dict=data)
        self._data_queue.put(
                (timestamp, data, origin)
        )
        return None

    def get_latest(self, origin, data):
        injected_settings = self.__mitm_mapper.request_latest(origin, "injected_settings")

        ids_iv = self.__mitm_mapper.request_latest(origin, "ids_iv")
        if ids_iv is not None:
            ids_iv = ids_iv.get("values", None)
        response = {"ids_iv": ids_iv, "injected_settings": injected_settings}
        return json.dumps(response)

    def received_data_worker(self):
        while True:
            item = self._data_queue.get()
            items_left = self._data_queue.qsize()
            logger.debug("MITM data processing worker retrieved data. Queue length left afterwards: {}", str(items_left))
            if items_left > 50:  # TODO: no magic number
                logger.warning("MITM data processing workers are falling behind! Queue length: {}", str(items_left))
            if item is None:
                logger.warning("Received none from queue of data")
                break
            self.process_data(item[0], item[1], item[2])
            self._data_queue.task_done()

    @logger.catch
    def process_data(self, received_timestamp, data, origin):
        global application_args
        if origin not in self.__mitm_mapper.playerstats:
            logger.warning("Not processing data of {} since origin is unknown", str(origin))
            return
        type = data.get("type", None)
        if type:
            if type == 106:
                # process GetMapObject
                logger.success("Processing GMO received from {}. Received at {}", str(origin), str(datetime.fromtimestamp(received_timestamp)))

                if application_args.weather:
                    self._db_wrapper.submit_weather_map_proto(origin, data["payload"], received_timestamp)

                self._db_wrapper.submit_pokestops_map_proto(origin, data["payload"])
                self._db_wrapper.submit_gyms_map_proto(origin, data["payload"])
                self._db_wrapper.submit_raids_map_proto(origin, data["payload"])

                self._db_wrapper.submit_spawnpoints_map_proto(origin, data["payload"])
                mon_ids_iv = self.__mitm_mapper.get_mon_ids_iv(origin)
                self._db_wrapper.submit_mons_map_proto(origin, data["payload"], mon_ids_iv)
            elif type == 102:
                playerlevel = self.__mitm_mapper.playerstats[origin].get_level()
                if playerlevel >= 30:
                    logger.info("Processing Encounter received from {} at {}", str(origin), str(received_timestamp))
                    self._db_wrapper.submit_mon_iv(origin, received_timestamp, data["payload"])
                else:
                    logger.debug('Playerlevel lower than 30 - not processing encounter Data')
            elif type == 101:
                self._db_wrapper.submit_quest_proto(data["payload"])
            elif type == 104:
                self._db_wrapper.submit_pokestops_details_map_proto(data["payload"])
            elif type == 4:
                self.__mitm_mapper.playerstats[origin].gen_player_stats(data["payload"])
