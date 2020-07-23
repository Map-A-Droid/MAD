from functools import wraps
import gzip
import json
import sys
import time
import io
from multiprocessing import JoinableQueue, Process
from typing import Any, Union, Optional

from flask import Flask, Response, request, send_file
from gevent.pywsgi import WSGIServer

from mapadroid.mitm_receiver.MITMDataProcessor import MitmDataProcessor
from mapadroid.mitm_receiver.MitmMapper import MitmMapper
from mapadroid.utils import MappingManager
from mapadroid.utils.authHelper import check_auth
from mapadroid.utils.collections import Location
from mapadroid.utils.logging import LogLevelChanger, get_logger, LoggerEnums, get_origin_logger
from mapadroid.mad_apk import stream_package, parse_frontend, lookup_package_info, supported_pogo_version, APKType
from threading import RLock
from mapadroid.utils.autoconfig import origin_generator, RGCConfig, PDConfig


logger = get_logger(LoggerEnums.mitm)
app = Flask(__name__)


def validate_accepted(func) -> Any:
    @wraps(func)
    def decorated(self, *args, **kwargs):
        try:
            session_id: Optional[int] = kwargs.get('session_id', None)
            session_id = int(session_id)
            sql = "SELECT `status`\n"\
                  "FROM `autoconfig_registration`\n"\
                  "WHERE `session_id` = %s AND `instance_id` = %s"
            accepted = self._db_wrapper.autofetch_value(sql, (session_id, self._db_wrapper.instance_id))
            if accepted is None:
                return Response(status=404)
            if accepted == 0:
                return Response(status=406)
            return func(self, *args, **kwargs)
        except (TypeError, ValueError):
            return Response(status=404)
    return decorated


def validate_session(func) -> Any:
    @wraps(func)
    def decorated(self, *args, **kwargs):
        try:
            session_id: Optional[int] = kwargs.get('session_id', None)
            session_id = int(session_id)
            sql = "SELECT `status`\n"\
                  "FROM `autoconfig_registration`\n"\
                  "WHERE `session_id` = %s AND `instance_id` = %s"
            exists = self._db_wrapper.autofetch_value(sql, (session_id, self._db_wrapper.instance_id))
            if exists is None:
                return Response(status=404)
            return func(self, *args, **kwargs)
        except (TypeError, ValueError):
            return Response(status=404)
    return decorated


class EndpointAction(object):

    def __init__(self, action, application_args, mapping_manager: MappingManager, data_manager):
        self.action = action
        self.response = Response(status=200, headers={})
        self.application_args = application_args
        self.mapping_manager: MappingManager = mapping_manager
        self.__data_manager = data_manager

    def __call__(self, *args, **kwargs):
        logger.debug2("HTTP Request from {}", request.remote_addr)
        origin = request.headers.get('Origin')
        origin_logger = get_origin_logger(logger, origin=origin)
        abort = False
        if request.url_rule is not None and str(request.url_rule) == '/status/':
            auth = request.headers.get('Authorization', False)
            if self.application_args.mitm_status_password != "" and \
                    (not auth or auth != self.application_args.mitm_status_password):
                self.response = Response(status=500, headers={})
                abort = True
            else:
                abort = False
        elif 'autoconfig/' in request.url and str(request.url_rule):
            auth = request.headers.get('Authorization', None)
            if auth is None or not check_auth(logger, auth, self.application_args, self.mapping_manager.get_auths()):
                origin_logger.warning("Unauthorized attempt to POST from {}", request.remote_addr)
                self.response = Response(status=403, headers={})
                abort = True
        elif request.url is not None and str(request.url_rule) == '/origin_generator':
            auth = request.headers.get('Authorization', None)
            if auth is None or not check_auth(logger, auth, self.application_args, self.mapping_manager.get_auths()):
                origin_logger.warning("Unauthorized attempt to POST from {}", request.remote_addr)
                self.response = Response(status=403, headers={})
                abort = True
        elif request.url and ('download' in request.url or 'mymac' in request.url):
            auth = request.headers.get('Authorization', None)
            if auth is None or not check_auth(logger, auth, self.application_args, self.mapping_manager.get_auths()):
                origin_logger.warning("Unauthorized attempt to POST from {}", request.remote_addr)
                self.response = Response(status=403, headers={})
                abort = True
            devs = self.__data_manager.search('device', params={'origin': origin})
            if not devs:
                abort = False
                origin_logger.warning("Unauthorized attempt to POST from {}", request.remote_addr)
                self.response = Response(status=403, headers={})
        else:
            if origin is None:
                origin_logger.warning("Missing Origin header in request")
                self.response = Response(status=500, headers={})
                abort = True
            elif self.mapping_manager.get_all_devicemappings().keys() is not None and \
                    origin not in self.mapping_manager.get_all_devicemappings().keys():
                origin_logger.warning("MITMReceiver request without Origin or disallowed Origin")
                self.response = Response(status=403, headers={})
                abort = True
            elif self.mapping_manager.get_auths() is not None:
                auth = request.headers.get('Authorization', None)
                if auth is None or not check_auth(origin_logger, auth, self.application_args,
                                                  self.mapping_manager.get_auths()):
                    origin_logger.warning("Unauthorized attempt to POST from {}", request.remote_addr)
                    self.response = Response(status=403, headers={})
                    abort = True

        if not abort:
            try:
                content_encoding = request.headers.get('Content-Encoding', None)
                if content_encoding and content_encoding == "gzip":
                    # we need to unpack the data first
                    # https://stackoverflow.com/questions/28304515/receiving-gzip-with-flask
                    compressed_data = io.BytesIO(request.data)
                    text_data = gzip.GzipFile(fileobj=compressed_data, mode='r')
                    request_data = json.loads(text_data.read())
                else:
                    request_data = request.data

                content_type = request.headers.get('Content-Type', None)
                if content_type and content_type == "application/json":
                    request_data = json.loads(request_data)
                else:
                    request_data = request_data
                response_payload = self.action(origin, request_data, *args, **kwargs)
                if response_payload is None:
                    response_payload = ""
                if type(response_payload) is Response:
                    self.response = response_payload
                else:
                    self.response = Response(status=200, headers={"Content-Type": "application/json"})
                    self.response.data = response_payload
            except Exception as e:  # TODO: catch exact exception
                origin_logger.warning("Could not get JSON data from request: {}", e)
                self.response = Response(status=500, headers={})
        return self.response


class MITMReceiver(Process):
    def __init__(self, listen_ip, listen_port, mitm_mapper, args_passed, mapping_manager: MappingManager,
                 db_wrapper, data_manager, storage_obj, name=None, enable_configmode: Optional[bool] = False):
        Process.__init__(self, name=name)
        self.__application_args = args_passed
        self.__mapping_manager = mapping_manager
        self.__listen_ip = listen_ip
        self.__listen_port = listen_port
        self.__mitm_mapper: MitmMapper = mitm_mapper
        self.__data_manager = data_manager
        self.__hopper_mutex = RLock()
        self._db_wrapper = db_wrapper
        self.__storage_obj = storage_obj
        self._data_queue: JoinableQueue = JoinableQueue()
        self.worker_threads = []
        self.app = Flask("MITMReceiver")
        self.add_endpoint(endpoint='/get_addresses/', endpoint_name='get_addresses/',
                          handler=self.get_addresses,
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
        self.add_endpoint(endpoint='/mad_apk/<string:apk_type>/<string:apk_arch>/download',
                          endpoint_name='mad_apk/arch/download',
                          handler=self.mad_apk_download,
                          methods_passed=['GET'])
        self.add_endpoint(endpoint='/origin_generator',
                          endpoint_name='origin_generator/',
                          handler=self.origin_generator_endpoint,
                          methods_passed=['GET'])
        self.add_endpoint(endpoint='/autoconfig/register',
                          endpoint_name='autoconfig/register',
                          handler=self.autoconf_register,
                          methods_passed=['POST'])
        self.add_endpoint(endpoint='/autoconfig/mymac',
                          endpoint_name='autoconfig/mymac',
                          handler=self.autoconf_mymac,
                          methods_passed=['GET', 'POST'])
        self.add_endpoint(endpoint='/autoconfig/<int:session_id>/<string:operation>',
                          endpoint_name='autoconfig/status/operation',
                          handler=self.autoconfig_operation,
                          methods_passed=['GET', 'DELETE'])
        if not enable_configmode:
            self.add_endpoint(endpoint='/', endpoint_name='receive_protos', handler=self.proto_endpoint,
                              methods_passed=['POST'])
            self.add_endpoint(endpoint='/get_latest_mitm/', endpoint_name='get_latest_mitm/',
                              handler=self.get_latest,
                              methods_passed=['GET'])
            self.add_endpoint(endpoint='/status/', endpoint_name='status/', handler=self.status,
                              methods_passed=['GET'])
            for i in range(self.__application_args.mitmreceiver_data_workers):
                data_processor: MitmDataProcessor = MitmDataProcessor(self._data_queue, self.__application_args,
                                                                      self.__mitm_mapper, db_wrapper,
                                                                      name='MITMReceiver-%s' % str(i))
                data_processor.start()
                self.worker_threads.append(data_processor)

    def shutdown(self):
        logger.info("MITMReceiver stop called...")
        logger.info("Adding None to queue")
        if self._data_queue:
            for i in range(self.__application_args.mitmreceiver_data_workers):
                self._data_queue.put(None)
        logger.info("Trying to join workers...")
        for worker_thread in self.worker_threads:
            worker_thread.terminate()
            worker_thread.join()
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

    def add_endpoint(self, endpoint=None, endpoint_name=None, handler=None, methods_passed=None):
        if methods_passed is None:
            logger.error("Invalid REST method specified")
            sys.exit(1)
        self.app.add_url_rule(endpoint, endpoint_name,
                              EndpointAction(handler, self.__application_args, self.__mapping_manager,
                                             self.__data_manager),
                              methods=methods_passed)

    def proto_endpoint(self, origin: str, data: Union[dict, list]):
        origin_logger = get_origin_logger(logger, origin=origin)
        origin_logger.debug2("Receiving proto")
        origin_logger.debug4("Proto data received {}", data)
        if isinstance(data, list):
            # list of protos... we hope so at least....
            origin_logger.debug2("Receiving list of protos")
            for proto in data:
                self.__handle_proto_data_dict(origin, proto)
        elif isinstance(data, dict):
            origin_logger.debug2("Receiving single proto")
            # single proto, parse it...
            self.__handle_proto_data_dict(origin, data)

        self.__mitm_mapper.set_injection_status(origin)

    def __handle_proto_data_dict(self, origin: str, data: dict) -> None:
        origin_logger = get_origin_logger(logger, origin=origin)
        proto_type = data.get("type", None)
        if proto_type is None or proto_type == 0:
            origin_logger.warning("Could not read method ID. Stopping processing of proto")
            return

        timestamp: float = data.get("timestamp", int(time.time()))
        location_of_data: Location = Location(data.get("lat", 0.0), data.get("lng", 0.0))
        if (location_of_data.lat > 90 or location_of_data.lat < -90 or
                location_of_data.lng > 180 or location_of_data.lng < -180):
            origin_logger.warning("Received invalid location in data: {}", location_of_data)
            location_of_data: Location = Location(0, 0)
        self.__mitm_mapper.update_latest(origin, timestamp_received_raw=timestamp,
                                         timestamp_received_receiver=time.time(), key=proto_type, values_dict=data,
                                         location=location_of_data)
        origin_logger.debug2("Placing data received to data_queue")
        self._data_queue.put((timestamp, data, origin))

    def get_latest(self, origin, data):
        injected_settings = self.__mitm_mapper.request_latest(
            origin, "injected_settings")

        ids_iv = self.__mitm_mapper.request_latest(origin, "ids_iv")
        if ids_iv is not None:
            ids_iv = ids_iv.get("values", None)

        safe_items = self.__mitm_mapper.get_safe_items(origin)
        level_mode = self.__mitm_mapper.get_levelmode(origin)

        ids_encountered = self.__mitm_mapper.request_latest(
            origin, "ids_encountered")
        if ids_encountered is not None:
            ids_encountered = ids_encountered.get("values", None)
        response = {"ids_iv": ids_iv, "injected_settings": injected_settings,
                    "ids_encountered": ids_encountered, "safe_items": safe_items,
                    "lvl_mode": level_mode}
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
        parsed = parse_frontend(**kwargs)
        if type(parsed) == Response:
            return parsed
        apk_type, apk_arch = parsed
        return stream_package(self._db_wrapper, self.__storage_obj, apk_type, apk_arch)

    def mad_apk_info(self, *args, **kwargs) -> Response:
        parsed = parse_frontend(**kwargs)
        if type(parsed) == Response:
            return parsed
        apk_type, apk_arch = parsed
        (msg, status_code) = lookup_package_info(self.__storage_obj, apk_type, apk_arch)
        if msg:
            if apk_type == APKType.pogo and not supported_pogo_version(apk_arch, msg.version):
                return Response(status=406, response='Supported version not installed')
            return Response(status=status_code, response=msg.version)
        else:
            return Response(status=status_code)

    def origin_generator_endpoint(self, *args, **kwargs):
        return origin_generator(self.__data_manager, self._db_wrapper, **kwargs)

    # ========================================
    # ============== AutoConfig ==============
    # ========================================
    @validate_session
    def autoconfig_complete(self, *args, **kwargs) -> Response:
        session_id: Optional[int] = kwargs.get('session_id', None)
        try:
            info = {
                'session_id': session_id,
                'instance_id': self._db_wrapper.instance_id
            }
            self._db_wrapper.autoexec_delete('autoconfig_registration', info)
            return Response(status=200)
        except Exception:
            logger.opt(exception=True).error('Unable to delete session')
            return Response(status=404)

    @validate_accepted
    def autoconfig_get_config(self, *args, **kwargs) -> Response:
        session_id: Optional[int] = kwargs.get('session_id', None)
        operation: Optional[str] = kwargs.get('operation', None)
        try:
            sql = "SELECT sd.`name`\n"\
                  "FROM `settings_device` sd\n"\
                  "INNER JOIN `autoconfig_registration` ar ON ar.`device_id` = sd.`device_id`\n"\
                  "WHERE ar.`session_id` = %s AND ar.`instance_id` = %s"
            origin = self._db_wrapper.autofetch_value(sql, (session_id, self._db_wrapper.instance_id))
            if operation in ['pd', 'rgc']:
                if operation == 'pd':
                    config = PDConfig(self._db_wrapper, self.__application_args, self.__data_manager)
                else:
                    config = RGCConfig(self._db_wrapper, self.__application_args, self.__data_manager)
                return send_file(config.generate_config(origin), as_attachment=True, attachment_filename='conf.xml',
                                 mimetype='application/xml')
            elif operation in ['google']:
                sql = "SELECT ag.`email`, ag.`pwd`\n"\
                      "FROM `autoconfig_google` ag\n"\
                      "INNER JOIN `autoconfig_registration` ar ON ar.`device_id` = ag.`device_id`\n"\
                      "WHERE ar.`session_id` = %s and ag.`instance_id` = %s"
                login = self._db_wrapper.autofetch_row(sql, (session_id, self._db_wrapper.instance_id))
                return Response(status=200, response='\n'.join([login['email'], login['pwd']]))
            elif operation == 'origin':
                return Response(status=200, response=origin)
        except Exception:
            logger.opt(exception=True).critical('Unable to process autoconfig')
            return Response(status=406)

    def autoconf_mymac(self, *args, **kwargs) -> Response:
        origin = request.headers.get('Origin')
        if origin is None:
            return Response(status=404)
        devs = self.__data_manager.search('device', params={'origin': origin})
        device = None
        for _, dev in devs.items():
            if origin == dev['origin']:
                device = dev
                break
        if not device:
            return Response(status=404)
        if request.method == 'GET':
            try:
                return Response(status=200, response=device['mac_address'])
            except KeyError:
                return Response(status=200, response="")
        elif request.method == 'POST':
            data = request.data
            if not data:
                return Response(status=400, response='No MAC provided')
            device['mac_address'] = data
            device.save()
            return Response(status=200)
        else:
            return Response(status=405)

    def autoconfig_operation(self, *args, **kwargs) -> Response:
        operation: Optional[str] = kwargs.get('operation', None)
        if operation is None:
            return Response(status=404)
        if request.method == 'GET':
            if operation == 'status':
                return self.autoconfig_status(*args, **kwargs)
            elif operation in ['pd', 'rgc', 'google', 'origin']:
                return self.autoconfig_get_config(*args, **kwargs)
        elif request.method == 'DELETE':
            if operation == 'complete':
                return self.autoconfig_complete(*args, **kwargs)
        return Response(status=404)

    def autoconf_register(self, *args, **kwargs) -> Response:
        """ Device attempts to register with MAD.  Returns a session id for tracking future calls """
        origin: Optional[str] = kwargs.get('Origin', None)
        walker_id: Optional[int] = kwargs.get('walker_id', None)
        walkers: dict[int, dict] = self.__data_manager.get_root_resource('walker')
        # Validate its a valid walker (If any)
        if walker_id is not None:
            try:
                walker_id = int(walker_id)
                walkers[walker_id]
            except KeyError:
                return Response(404, response='Walker ID not found')
            except ValueError:
                return Response(status=404, response='Walker must be an integer')
        status = 0
        #  TODO - auto-accept list
        if False:
            status = 1
        register_data = {
            'name': origin,
            'walker_id': walker_id,
            'status': status,
            'ip': get_actual_ip(request),
            'instance_id': self._db_wrapper.instance_id
        }
        session_id = self._db_wrapper.autoexec_insert('autoconfig_registration', register_data)
        return Response(status=201, response=str(session_id))

    @validate_accepted
    def autoconfig_status(self, *args, **kwargs) -> Response:
        session_id: Optional[int] = kwargs.get('session_id', None)
        update_data = {
            'ip': get_actual_ip(request)
        }
        where = {
            'session_id': session_id,
            'instance_id': self._db_wrapper.instance_id
        }
        self._db_wrapper.autoexec_update('autoconfig_registration', update_data, where_keyvals=where)
        return Response(status=201)


def get_actual_ip(request):
    if request.environ.get('HTTP_X_FORWARDED_FOR') is None:
        return request.environ['REMOTE_ADDR']
    else:
        return request.environ['HTTP_X_FORWARDED_FOR']
