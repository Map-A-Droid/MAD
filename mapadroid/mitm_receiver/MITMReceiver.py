import json
import sys
import time
from multiprocessing import JoinableQueue, Process
from typing import Union

from flask import Flask, Response, request
from gevent.pywsgi import WSGIServer

from mapadroid.mitm_receiver.MITMDataProcessor import MitmDataProcessor
from mapadroid.mitm_receiver.MitmMapper import MitmMapper
from mapadroid.utils import MappingManager
from mapadroid.utils.authHelper import check_auth
from mapadroid.utils.logging import LogLevelChanger, logger
from mapadroid.utils.apk_util import download_file, convert_to_backend, get_apk_list
from threading import RLock
import mapadroid.data_manager

app = Flask(__name__)


class EndpointAction(object):

    def __init__(self, action, application_args, mapping_manager: MappingManager):
        self.action = action
        self.response = Response(status=200, headers={})
        self.application_args = application_args
        self.mapping_manager: MappingManager = mapping_manager

    def __call__(self, *args, **kwargs):
        logger.debug3("HTTP Request from {}".format(str(request.remote_addr)))
        origin = request.headers.get('Origin')
        abort = False
        if request.url_rule is not None and str(request.url_rule) == '/status/':
            auth = request.headers.get('Authorization', False)
            if self.application_args.mitm_status_password != "" and \
                    (not auth or auth != self.application_args.mitm_status_password):
                self.response = Response(status=500, headers={})
                abort = True
            else:
                abort = False
        elif request.url is not None and str(request.url_rule) == '/origin_generator':
            auth = request.headers.get('Authorization', None)
            if auth is None or not check_auth(auth, self.application_args,
                                              self.mapping_manager.get_auths()):
                logger.warning(
                    "Unauthorized attempt to POST from {}", str(request.remote_addr))
                self.response = Response(status=403, headers={})
                abort = True
        else:
            if not origin:
                logger.warning("Missing Origin header in request")
                self.response = Response(status=500, headers={})
                abort = True
            elif (self.mapping_manager.get_all_devicemappings().keys() is not None
                  and (origin is None or origin not in self.mapping_manager.get_all_devicemappings().keys())):
                logger.warning("MITMReceiver request without Origin or disallowed Origin: {}".format(origin))
                self.response = Response(status=403, headers={})
                abort = True
            elif self.mapping_manager.get_auths() is not None:
                auth = request.headers.get('Authorization', None)
                if auth is None or not check_auth(auth, self.application_args,
                                                  self.mapping_manager.get_auths()):
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
                response_payload = self.action(origin, request_data, *args, **kwargs)
                if response_payload is None:
                    response_payload = ""
                if type(response_payload) is Response:
                    self.response = response_payload
                else:
                    self.response = Response(status=200, headers={"Content-Type": "application/json"})
                    self.response.data = response_payload
            except Exception as e:  # TODO: catch exact exception
                logger.warning(
                    "Could not get JSON data from request: {}", str(e))
                self.response = Response(status=500, headers={})
        return self.response


class MITMReceiver(Process):
    def __init__(self, listen_ip, listen_port, mitm_mapper, args_passed, mapping_manager: MappingManager,
                 db_wrapper, data_manager, name=None):
        Process.__init__(self, name=name)
        self.__application_args = args_passed
        self.__mapping_manager = mapping_manager
        self.__listen_ip = listen_ip
        self.__listen_port = listen_port
        self.__mitm_mapper: MitmMapper = mitm_mapper
        self.__data_manager = data_manager
        self.__hopper_mutex = RLock()
        self.app = Flask("MITMReceiver")
        self.add_endpoint(endpoint='/', endpoint_name='receive_protos', handler=self.proto_endpoint,
                          methods_passed=['POST'])
        self.add_endpoint(endpoint='/get_latest_mitm/', endpoint_name='get_latest_mitm/',
                          handler=self.get_latest,
                          methods_passed=['GET'])
        self.add_endpoint(endpoint='/get_addresses/', endpoint_name='get_addresses/',
                          handler=self.get_addresses,
                          methods_passed=['GET'])
        self.add_endpoint(endpoint='/status/', endpoint_name='status/', handler=self.status,
                          methods_passed=['GET'])
        self.add_endpoint(endpoint='/mad_apk/<string:apk_type>',
                          endpoint_name='mad_apk/info',
                          handler=self.mad_apk_info,
                          methods_passed=['GET'])
        self.add_endpoint(endpoint='/mad_apk/<string:apk_type>/<string:apk_arch>',
                          endpoint_name='mad_apk/arch/info',
                          handler=self.mad_apk_info,
                          methods_passed=['GET'])
        self.add_endpoint(endpoint='/mad_apk/<string:apk_type>/download',
                          endpoint_name='mad_apk/download',
                          handler=self.mad_apk_download,
                          methods_passed=['GET'])
        self.add_endpoint(endpoint='/mad_apk/<string:apk_type>/download',
                          endpoint_name='mad_apk/arch/download',
                          handler=self.mad_apk_download,
                          methods_passed=['GET'])
        self.add_endpoint(endpoint='/origin_generator',
                          endpoint_name='origin_generator/',
                          handler=self.origin_generator,
                          methods_passed=['GET'])

        self._data_queue: JoinableQueue = JoinableQueue()
        self._db_wrapper = db_wrapper
        self.worker_threads = []
        for i in range(self.__application_args.mitmreceiver_data_workers):
            data_processor: MitmDataProcessor = MitmDataProcessor(self._data_queue, self.__application_args,
                                                                  self.__mitm_mapper, db_wrapper,
                                                                  name='MITMReceiver-%s' % str(i))
            data_processor.start()
            self.worker_threads.append(data_processor)

    def shutdown(self):
        logger.info("MITMReceiver stop called...")
        logger.info("Adding None to queue")
        for i in range(self.__application_args.mitmreceiver_data_workers):
            self._data_queue.put(None)
        logger.info("Trying to join workers...")
        for t in self.worker_threads:
            t.terminate()
            t.join()
        self._data_queue.close()
        logger.info("Workers stopped...")

    def run(self):
        httpsrv = WSGIServer((self.__listen_ip, int(
            self.__listen_port)), self.app.wsgi_app, log=LogLevelChanger)
        try:
            httpsrv.serve_forever()
        except KeyboardInterrupt:
            httpsrv.close()
            logger.info("Received STOP signal in MITMReceiver")

    def add_endpoint(self, endpoint=None, endpoint_name=None, handler=None, options=None,
                     methods_passed=None):
        if methods_passed is None:
            logger.error("Invalid REST method specified")
            sys.exit(1)
        self.app.add_url_rule(endpoint, endpoint_name,
                              EndpointAction(handler, self.__application_args, self.__mapping_manager),
                              methods=methods_passed)

    def proto_endpoint(self, origin: str, data: Union[dict, list]):
        logger.debug2("Receiving proto from {}".format(origin))
        logger.debug4("Proto data received from {}: {}".format(origin, str(data)))
        if isinstance(data, list):
            # list of protos... we hope so at least....
            logger.debug2("Receiving list of protos")
            for proto in data:
                self.__handle_proto_data_dict(origin, proto)
        elif isinstance(data, dict):
            logger.debug2("Receiving single proto")
            # single proto, parse it...
            self.__handle_proto_data_dict(origin, data)

        self.__mitm_mapper.set_injection_status(origin)

    def __handle_proto_data_dict(self, origin: str, data: dict) -> None:
        type = data.get("type", None)
        if type is None or type == 0:
            logger.warning(
                "Could not read method ID. Stopping processing of proto")
            return

        timestamp: float = data.get("timestamp", int(time.time()))
        self.__mitm_mapper.update_latest(
            origin, timestamp_received_raw=timestamp, timestamp_received_receiver=time.time(), key=type,
            values_dict=data)
        logger.debug3("Placing data received by {} to data_queue".format(origin))
        self._data_queue.put(
            (timestamp, data, origin)
        )

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

    def status(self, origin, data):
        origin_return: dict = {}
        process_return: dict = {}
        data_return: dict = {}
        process_count: int = 0
        for origin in self.__mapping_manager.get_all_devicemappings().keys():
            origin_return[origin] = {}
            origin_return[origin]['injection_status'] = self.__mitm_mapper.get_injection_status(origin)
            origin_return[origin]['latest_data'] = self.__mitm_mapper.request_latest(origin,
                                                                                     'timestamp_last_data')
            origin_return[origin]['mode_value'] = self.__mitm_mapper.request_latest(origin,
                                                                                    'injected_settings')
            origin_return[origin][
                'last_possibly_moved'] = self.__mitm_mapper.get_last_timestamp_possible_moved(origin)

        for process in self.worker_threads:
            process_return['MITMReceiver-' + str(process_count)] = {}
            process_return['MITMReceiver-' + str(process_count)]['queue_length'] = process.get_queue_items()
            process_count += 1

        data_return['origin_status'] = origin_return
        data_return['process_status'] = process_return

        return json.dumps(data_return)

    def mad_apk_download(self, *args, **kwargs):
        apk_type = kwargs.get('apk_type', None)
        apk_arch = kwargs.get('apk_arch', None)
        apk_type, apk_arch = convert_to_backend(apk_type, apk_arch)
        return download_file(self._db_wrapper, apk_type, apk_arch)

    def mad_apk_info(self, *args, **kwargs):
        apk_type = kwargs.get('apk_type', None)
        apk_arch = kwargs.get('apk_arch', None)
        apk_type, apk_arch = convert_to_backend(apk_type, apk_arch)
        versions = {}
        (apks, status_code) = get_apk_list(self._db_wrapper, apk_type, apk_arch)
        if status_code == 200:
            if 'filename' in apks:
                versions = apks['version']
            else:
                return Response(status=400, response='Version not specified or invalid')
        elif status_code == 404:
            return Response(status=400, response='APK has not been downloaded')
        else:
            return Response(status=400, response='Please specify APK and Architecture')
        return versions

    def origin_generator(self, *args, **kwargs):
        origin = request.headers.get('OriginBase', None)
        walker_id = request.headers.get('walker', None)
        pool_id = request.headers.get('pool', None)
        device = mapadroid.data_manager.modules.MAPPINGS['device'](self.__data_manager)
        if origin is None:
            return Response(status=400, response='Please specify an Origin Prefix')
        with self.__hopper_mutex:
            last_id_sql = "SELECT `last_id` FROM `origin_hopper` WHERE `origin` = %s"
            last_id = self._db_wrapper.autofetch_value(last_id_sql, (origin,))
            if last_id is None:
                last_id = 0
            walkers = self.__data_manager.get_root_resource('walker')
            if len(walkers) == 0:
                    return Response(status=400, response='No walkers configured')
            if walker_id is not None:
                try:
                    walker_id = int(walker_id)
                    walkers[walker_id]
                except KeyError:
                    return Response(404, response='Walker ID not found')
                except ValueError:
                    return Response(status=404, response='Walker must be an integer')
            else:
                walker_id = next(iter(walkers))
            device['walker'] = walker_id
            if pool_id is not None:
                pools = self.__data_manager.get_root_resource('devicepool')
                try:
                    pool_id = int(pool_id)
                    pools[pool_id]
                except KeyError:
                    return Response(404, response='Walker ID not found')
                except ValueError:
                    return Response(status=404, response='Walker must be an integer')
                device['pool'] = pool_id
            next_id = last_id + 1
            data = {
                'origin': origin,
                'last_id': next_id,
            }
            origin = '%s%s' % (origin, next_id,)
            self._db_wrapper.autoexec_insert('origin_hopper', data, optype="ON DUPLICATE")
            device['walker'] = walker_id
            device['origin'] = origin
            device.save()
            return origin