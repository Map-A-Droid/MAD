import copy
import json
from enum import IntEnum
from io import BytesIO
from typing import Any, Dict, List, NoReturn, Optional, Tuple, Union
from xml.sax.saxutils import escape

from flask import Response, url_for
from sqlalchemy.ext.asyncio import AsyncSession

from mapadroid.db.DbWrapper import DbWrapper
from mapadroid.db.helper.AutoconfigFileHelper import AutoconfigFileHelper
from mapadroid.db.helper.OriginHopperHelper import OriginHopperHelper
from mapadroid.db.helper.SettingsAuthHelper import SettingsAuthHelper
from mapadroid.db.helper.SettingsDevicepoolHelper import \
    SettingsDevicepoolHelper
from mapadroid.db.helper.SettingsPogoauthHelper import SettingsPogoauthHelper
from mapadroid.db.helper.SettingsWalkerHelper import SettingsWalkerHelper
from mapadroid.db.model import (AutoconfigFile, OriginHopper, SettingsAuth,
                                SettingsDevice, SettingsDevicepool,
                                SettingsPogoauth, SettingsWalker)
from mapadroid.mad_apk import get_apk_status


USER_READABLE_ERRORS = {
    str: 'string (MapADroid)',
    int: 'Integer (1,2,3)',
    float: 'Decimal (1.0, 1.5)',
    list: 'Comma-delimited list',
    bool: 'True|False'
}


class AutoConfIssues(IntEnum):
    no_ggl_login: int = 1
    origin_hopper_not_ready: int = 2
    auth_not_configured: int = 3
    pd_not_configured: int = 4
    rgc_not_configured: int = 5
    package_missing: int = 6


class AutoConfIssueGenerator(object):
    def __init__(self, db_wrapper: DbWrapper, args, storage_obj):
        self.warnings: List[AutoConfIssues] = []
        self.critical: List[AutoConfIssues] = []

        # TODO: Move to async start/init/create
        pogoauth_entries: List[SettingsPogoauth] = await SettingsPogoauthHelper.get_unassigned(session, instance_id)
        if len(pogoauth_entries) == 0 and not args.autoconfig_no_auth:
            self.warnings.append(AutoConfIssues.no_ggl_login)
        if not validate_hopper_ready(session, instance_id):
            self.critical.append(AutoConfIssues.origin_hopper_not_ready)
        auths: List[SettingsAuth] = await SettingsAuthHelper.get_all(session, self.db_wrapper.instance_id)
        if len(auths) == 0:
            self.warnings.append(AutoConfIssues.auth_not_configured)
        if not PDConfig(db_wrapper, args).configured:
            self.critical.append(AutoConfIssues.pd_not_configured)
        if not RGCConfig(db_wrapper, args).configured:
            self.critical.append(AutoConfIssues.rgc_not_configured)
        missing_packages = []
        for _, apkpackages in get_apk_status(storage_obj).items():
            for _, package in apkpackages.items():
                if package.version is None:
                    missing_packages.append(package)
        if missing_packages:
            self.critical.append(AutoConfIssues.package_missing)

    def get_headers(self) -> Dict:
        headers: Dict[str, int] = {
            'X-Critical': json.dumps([issue.value for issue in self.critical]),
            'X-Warnings': json.dumps([issue.value for issue in self.warnings])
        }
        return headers

    def get_issues(self) -> Tuple[List[str], List[str]]:
        issues_warning = []
        issues_critical = []
        # Warning messages
        if AutoConfIssues.no_ggl_login in self.warnings:
            link = url_for('settings_pogoauth')
            anchor = f"<a class=\"alert-link\" href=\"{link}\">PogoAuth</a>"
            issues_warning.append("No available Google logins for auto creation of devices. Configure through "
                                  f"{anchor}")
        if AutoConfIssues.auth_not_configured in self.warnings:
            link = url_for('settings_auth')
            anchor = f"<a class=\"alert-link\" href=\"{link}\">Auth</a>"
            issues_warning.append(f"No auth configured which is a potential security risk. Configure through {anchor}")
        # Critical messages
        if AutoConfIssues.origin_hopper_not_ready in self.critical:
            link = url_for('settings_walkers')
            anchor = f"<a class=\"alert-link\" href=\"{link}\">Walker</a>"
            issues_critical.append(f"No walkers configured. Configure through {anchor}")
        if AutoConfIssues.pd_not_configured in self.critical:
            link = url_for('autoconf_pd')
            anchor = f"<a class=\"alert-link\" href=\"{link}\">PogoDroid Configuration</a>"
            issues_critical.append(f"PogoDroid is not configured. Configure through {anchor}")
        if AutoConfIssues.rgc_not_configured in self.critical:
            link = url_for('autoconf_rgc')
            anchor = f"<a class=\"alert-link\" href=\"{link}\">RemoteGPSController Configuration</a>"
            issues_critical.append(f"RGC is not configured. Configure through {anchor}")
        if AutoConfIssues.package_missing in self.critical:
            link = url_for('mad_apks')
            anchor = f"<a class=\"alert-link\" href=\"{link}\">MADmin Packages</a>"
            issues_critical.append(f"Missing one or more required packages. Configure through {anchor}")
        return issues_warning, issues_critical

    def has_blockers(self) -> bool:
        return len(self.critical) > 0


async def validate_hopper_ready(session: AsyncSession, instance_id: int) -> bool:
    walkers: List[SettingsWalker] = await SettingsWalkerHelper.get_all(session, instance_id)
    return len(walkers) > 0


# TODO: Singleton for the instance ID?
async def origin_generator(session: AsyncSession, instance_id: int, *args, **kwargs) -> Union[SettingsDevice, Response]:
    origin = kwargs.get('OriginBase', None)
    walker_id = kwargs.get('walker', None)
    if walker_id is not None:
        try:
            walker_id: int = int(walker_id)
        except ValueError:
            return Response(status=404, response='"walker" value must be an integer')
    pool_id = kwargs.get('pool', None)
    if pool_id is not None:
        try:
            pool_id: int = int(pool_id)
        except ValueError:
            return Response(status=404, response='"pool" value must be an integer')
    is_ready = validate_hopper_ready(session, instance_id)
    if not is_ready:
        return Response(status=404, response='Unable to verify hopper. Likely no walkers have been configured at all.')
    if origin is None:
        return Response(status=400, response='Please specify an Origin Prefix')
    walkers: List[SettingsWalker] = await SettingsWalkerHelper.get_all(session, instance_id)
    walker: Optional[SettingsWalker] = None
    if walker_id is not None:
        for possible_walker in walkers:
            if possible_walker.walker_id == walker_id:
                walker = possible_walker
                break
        if walker is None:
            return Response(status=404, response='Walker ID not found')
    else:
        walker = walkers[0]
    if pool_id is not None:
        pool: Optional[SettingsDevicepool] = await SettingsDevicepoolHelper.get(session, pool_id)
        if pool is None:
            return Response(status=404, response='Devicepool not found')
    origin_hopper: Optional[OriginHopper] = await OriginHopperHelper.get(session, origin)
    if not origin_hopper:
        origin_hopper = OriginHopper()
        origin_hopper.origin = origin
    next_id = origin_hopper.last_id + 1 if origin_hopper is not None else 0
    origin_hopper.last_id = next_id
    session.add(origin_hopper)

    origin = '%s%03d' % (origin, next_id,)
    device: SettingsDevice = SettingsDevice()
    device.pool_id = pool_id
    device.walker_id = walker.walker_id
    device.name = origin
    session.add(device)
    return device


class AutoConfIssue(Exception):
    def __init__(self, issues):
        super().__init__()
        self.issues = issues


class AutoConfigCreator:
    origin_field: str = None

    def __init__(self, db: DbWrapper, args):
        self._db: DbWrapper = db
        self._args = args
        self.contents: dict[str, Any] = {}
        self.configured: bool = False
        self.load_config()

    def delete(self):
        config: Optional[AutoconfigFile] = await AutoconfigFileHelper.get(session, self.source, instace_id)
        if config is not None:
            session.delete(config)

    def generate_config(self, origin: str) -> str:
        origin_config = self.get_config()
        origin_config[self.origin_field] = origin
        conv_xml = ["<?xml version=\"1.0\" encoding=\"utf-8\" standalone=\"yes\" ?>", "<map>"]
        for _, sect_conf in self.sections.items():
            for key, elem in sect_conf.items():
                if key not in origin_config:
                    continue
                elem_type = "string"
                value = escape(str(origin_config[key]))
                if elem['expected'] == bool:
                    elem_type = "boolean"
                xml_elem = "<{} name=\"{}\"".format(elem_type, key)
                if elem['expected'] == bool:
                    xml_elem += " value=\"{}\" />".format(value)
                else:
                    xml_elem += ">{}</{}>".format(value, elem_type)
                conv_xml.append('    {}'.format(xml_elem))
        conv_xml.append('</map>')
        # TODO: Threaded exec needed?
        return BytesIO('\n'.join(conv_xml).encode('utf-8'))

    async def get_config(self) -> dict:
        tmp_config: dict = copy.copy(self.contents)
        auth: Optional[SettingsAuth] = None
        try:
            auth: Optional[SettingsAuth] = await SettingsAuthHelper.get(session, tmp_config['mad_auth'])
            del tmp_config['mad_auth']
        except KeyError:
            auth = None
        if auth is not None:
            tmp_config['auth_username'] = auth.username
            tmp_config['auth_password'] = auth.password
            tmp_config['switch_enable_auth_header'] = True
        else:
            tmp_config['switch_enable_auth_header'] = False
            tmp_config['auth_username'] = ""
            tmp_config['auth_password'] = ""
        return tmp_config

    async def load_config(self) -> NoReturn:
        try:
            config: Optional[AutoconfigFile] = await AutoconfigFileHelper.get(session, instance_id, source)
            if config is not None:
                self.contents = json.loads(config.data)
                self.configured = True
            else:
                self.contents = {}
        except json.decoder.JSONDecodeError:
            self.contents = {}
        for _, sect_conf in self.sections.items():
            for key, elem in sect_conf.items():
                if key not in self.contents:
                    self.contents[key] = elem['default']
                    continue

    def save_config(self, user_vals: dict) -> NoReturn:
        self.validate(user_vals)
        await AutoconfigFileHelper.insert_or_update(session, self._db.instance_id, self.source, json.dumps(self.contents))

    def validate(self, user_vals: dict) -> bool:
        processed = []
        missing: List[str] = []
        invalid: List[str] = []
        for sect_conf in self.sections.values():
            for key, elem in sect_conf.items():
                processed.append(key)
                if elem['required'] and key not in user_vals:
                    if key not in self.contents:
                        missing.append(key)
                    continue
                if elem['required'] and user_vals[key] in [None, ""]:
                    if key not in self.contents:
                        missing.append(key)
                        continue
                try:
                    check_func = elem['expected']
                    if elem['expected'] == 'bool':
                        if user_vals[key] not in [True, False]:
                            invalid.append((key, USER_READABLE_ERRORS[bool]))
                    self.contents[key] = check_func(user_vals[key])
                except KeyError:
                    if key not in self.contents:
                        self.contents[key] = elem['default'] if elem['default'] not in ['None', None] else ""
                except (TypeError, ValueError):
                    invalid.append((key, USER_READABLE_ERRORS[check_func]))
        unknown = set(list(user_vals.keys())) - set(processed)
        try:
            invalid_dest = ['127.0.0.1', '0.0.0.0']
            for dest in invalid_dest:
                if dest in self.contents[self.host_field]:
                    invalid.append((self.host_field, "Routable address from outside the server"))
        except KeyError:
            pass
        issues = {}
        if missing:
            issues['missing'] = missing
        if invalid:
            issues['invalid'] = invalid
        if unknown:
            issues['unknown'] = unknown
        if issues:
            raise AutoConfIssue(issues)
        return True


class RGCConfig(AutoConfigCreator):
    host_field = "websocket_uri"
    origin_field = "websocket_origin"
    source = "rgc"
    sections = {
        "Socket": {
            "websocket_uri": {
                "title": "Websocket URI to connect to",
                "type": str,
                "expected": str,
                "default": "ws://",
                "summary": None,
                "required": True
            },
            "mad_auth": {
                "title": "Basic Authentication",
                "type": "authselect",
                "expected": int,
                "default": None,
                "summary": "Authentication credentials to use when performing basic auth",
                "required": False,
            },
            "websocket_origin": {
                "hidden": True,
                "title": "Websocket Origin",
                "type": str,
                "expected": str,
                "default": "",
                "summary": "Origin field of the header. This can be used as an identifier. Alphanumeric only.",
                "required": True
            },
            "switch_enable_auth_header": {
                "hidden": True,
                "title": "Enable Basic Auth header",
                "type": "bool",
                "expected": bool,
                "default": False,
                "summary": "For additional security, some servers may ask for basic auth to be sent with each "
                           "request for authorization. Keep in mind: if the connection is not secured via TLS (wss), "
                           "anyone could read the password.",
                "required": False
            },
            "auth_username": {
                "hidden": True,
                "title": "Username",
                "type": str,
                "expected": str,
                "default": "",
                "summary": None,
                "required": False
            },
            "auth_password": {
                "hidden": True,
                "title": "Password",
                "type": str,
                "expected": str,
                "default": "",
                "summary": None,
                "required": False
            }
        },
        "Rooted Devices": {
            "reset_google_play_services": {
                "title": "Reset GMS data",
                "type": "bool",
                "expected": bool,
                "enabled": False,
                "default": False,
                "summary": "Disabled for now...<br>"
                           "Resets Google Play Services data.<br>"
                           "This will STOP Google Play Services. Executed upon service start.<br>"
                           "Any apps relying on GMS will need to be restarted.<br>"
                           "Helps against rubberbanding.",
                "required": False
            },
            "oom_adj_override": {
                "title": "Override OOM value",
                "type": "bool",
                "expected": bool,
                "default": True,
                "summary": "Overrides the oom_adj value to reduce the possibility of the process being killed when "
                           "the system runs out of memory.",
                "required": False
            }
        },
        "Location": {
            "reset_agps_continuously": {
                "title": "Reset AGPS data continuously",
                "type": "bool",
                "expected": bool,
                "default": False,
                "summary": "Resets the AGPS data with every location update",
                "required": False
            },
            "reset_agps_once": {
                "title": "Reset AGPS data once",
                "type": "bool",
                "expected": bool,
                "default": False,
                "summary": "Resets AGPS data once at startup of services",
                "required": False
            },
            "use_mock_location": {
                "title": "Use Android Mock location",
                "type": "bool",
                "expected": bool,
                "default": True,
                "summary": "Requires RGC to be set as Mocking app in developer options",
                "required": False
            },
            "suspended_mocking": {
                "title": "Suspended mocking",
                "type": "bool",
                "expected": bool,
                "default": False,
                "summary": "May help against rubberbanding / location smoothing",
                "required": False
            },
            "location_overwrite_method": {
                "title": "location_overwrite_method",
                "type": "option",
                "values": ["Minimal", "Common", "Indirect"],
                "expected": str,
                "default": "Minimal",
                "summary": "Defines how many providers are overwritten (also known as indirect mocking). Minimal "
                           "(only GPS), Common (GPS, Network, Passive)",
                "required": False
            },
            "overwrite_fused": {
                "title": "Overwrite fused",
                "type": "bool",
                "expected": bool,
                "default": False,
                "summary": "Also overwrite fused provider",
                "required": False
            },
        },
        "General": {
            "boot_startup": {
                "title": "Start on boot",
                "type": "bool",
                "expected": bool,
                "default": True,
                "summary": "Start app on boot",
                "required": False
            },
            "boot_delay": {
                "title": "Start RGC delayed by X seconds",
                "type": int,
                "expected": int,
                "default": 40,
                "summary": "Start app on boot",
                "required": False
            },
            "autostart_services": {
                "title": "Start services on appstart",
                "type": "bool",
                "expected": bool,
                "default": True,
                "summary": "Automatically start the services when the app is opened",
                "required": False
            }
        }
    }

    def load_config(self) -> NoReturn:
        super().load_config()
        if self.contents['websocket_uri'] in ['ws://', '']:
            self.contents['websocket_uri'] = 'ws://{}:{}'.format(self._args.ws_ip, self._args.ws_port)
        auths: List[SettingsAuth] = await SettingsAuthHelper.get_all(session, self._db.instance_id)
        if len(auths) > 0:
            self.sections['Socket']['mad_auth']['required'] = True


class PDConfig(AutoConfigCreator):
    host_field = "post_destination"
    origin_field = "post_origin"
    source = "pd"
    sections = {
        "MAD Backend": {
            "user_id": {
                "title": "Backend User",
                "type": str,
                "expected": str,
                "default": "",
                "summary": "Username for logging into the MAD backend",
                "required": True
            },
            "auth_token": {
                "title": "Backend Device Password",
                "type": str,
                "expected": str,
                "default": "",
                "summary": "Device password created in the MAD backend",
                "required": True
            },
        },
        "External Communication": {
            "switch_disable_external_communication": {
                "title": "Disable external communication",
                "type": "bool",
                "expected": bool,
                "default": False,
                "summary": "Disables sending data to servers entirely.",
                "required": False
            },
            "post_timeout_ms_connect": {
                "title": "Connect timeout",
                "type": int,
                "expected": int,
                "default": 10000,
                "summary": "Time in ms until a timeout while connecting is triggered. 0 = no timeout, default 10000",
                "required": False
            },
            "post_timeout_ms_call": {
                "title": "Call timeout",
                "type": int,
                "expected": int,
                "default": 0,
                "summary": "Time in ms until a timeout for the entire call is triggered. Default 0 (no timeout). "
                           "Includes DNS resolving, redirects etc.",
                "required": False
            },
            "post_timeout_ms_read": {
                "title": "Read timeout",
                "type": int,
                "expected": int,
                "default": 10000,
                "summary": "Time in ms until a timeout for the read operation of the TCP socket and individual IO-ops "
                           " is triggered. Default 10000, 0 = no timeout.",
                "required": False
            },
            "post_timeout_ms_write": {
                "title": "Write timeout",
                "type": int,
                "expected": int,
                "default": 10000,
                "summary": "Time in ms until a timeout during IO write is triggered. Default 10000, 0 = no timeout.",
                "required": False
            },
            "switch_send_protos": {
                "title": "Send selected set of serialized data (json)",
                "type": "bool",
                "expected": bool,
                "default": True,
                "summary": "",
                "required": False
            },
            "post_aggregate_wait_ms": {
                "title": "Aggregation delay (serialized)",
                "type": int,
                "expected": int,
                "default": 500,
                "summary": "Time in ms until serialized protos are sent. Any protos received between the first proto "
                           "and the delay having passed will be aggregated in a POST. Default: 500ms",
                "required": False
            },
            "switch_gzip_post_data": {
                "title": "GZIP the serialized data that is to be posted.",
                "type": "bool",
                "expected": bool,
                "default": True,
                "summary": "",
                "required": False
            },
            "post_destination": {
                "title": "POST destination",
                "type": str,
                "expected": str,
                "default": "",
                "summary": "Destination to send data to",
                "required": True
            },
            "post_origin": {
                "hidden": True,
                "title": "POST Origin",
                "type": str,
                "expected": str,
                "default": "",
                "summary": "Origin field of the header. This can be used as an identifier. Alphanumeric only.",
                "required": True
            },
            "switch_send_raw_protos": {
                "title": "Send raw data (base64 encoded)",
                "type": "bool",
                "expected": bool,
                "default": False,
                "summary": "",
                "required": False
            },
            "post_raw_aggregate_wait_ms": {
                "title": "Aggregation delay (raw)",
                "type": int,
                "expected": int,
                "default": 500,
                "summary": "Time in ms until raw protos are sent. Any protos received between the first proto and the "
                           "delay having passed will be aggregated in a POST. Default: 500ms",
                "required": False
            },
            "switch_gzip_post_raw_data": {
                "title": "GZIP the raw data that is to be posted.",
                "type": "bool",
                "expected": bool,
                "default": True,
                "summary": "",
                "required": False
            },
            "post_destination_raw": {
                "title": "RAW POST Destination",
                "type": str,
                "expected": str,
                "default": "",
                "summary": "HTTP Endpoint to POST raw data to",
                "required": True
            },
            "switch_disable_last_sent": {
                "title": "Disable last sent notifications",
                "type": "bool",
                "expected": bool,
                "default": False,
                "summary": "Disable display of notifications of the last timestamp data was sent at. Attempts are also "
                           " logged for debugging of connectivity issues.",
                "required": False
            },
            "switch_popup_last_sent": {
                "title": "Heads up notification",
                "type": "bool",
                "expected": bool,
                "default": False,
                "summary": "Have a notification displayed as a heads-up notification every time data is sent",
                "required": False
            },
            "switch_enable_auth_header": {
                "hidden": True,
                "title": "Enable Basic Auth header",
                "type": "bool",
                "expected": bool,
                "default": False,
                "summary": "For additional security, some servers may ask for basic auth to be sent with each "
                           "request for authorization. Keep in mind: if the connection is not secured via TLS (wss), "
                           "anyone could read the password.",
                "required": False
            },
            "auth_username": {
                "hidden": True,
                "title": "Username",
                "type": str,
                "expected": str,
                "default": "",
                "summary": None,
                "required": False
            },
            "auth_password": {
                "hidden": True,
                "title": "Password",
                "type": str,
                "expected": str,
                "default": "",
                "summary": None,
                "required": False
            },
            "mad_auth": {
                "title": "Basic Authentication",
                "type": "authselect",
                "expected": int,
                "default": None,
                "summary": "Authentication credentials to use when performing basic auth",
                "required": False,
            },
        },
        "App": {
            "preference_inject_after_seconds": {
                "title": "Injection delay",
                "type": int,
                "expected": int,
                "default": 120,
                "summary": "Time in seconds to wait after a Pogo start to inject into the process. Default: 120s",
                "required": False
            },
            "toggle_injection_detection": {
                "title": "Injection detection",
                "type": "bool",
                "expected": bool,
                "default": False,
                "summary": "If you experience issues with injections/freezes/crashes, try this toggle which toggles "
                           "the detection method used.",
                "required": False
            },
            "disable_pogo_freeze_detection": {
                "title": "Disable Pogo freeze detection",
                "type": "bool",
                "expected": bool,
                "default": False,
                "summary": "If no data has been received for some time, a restart is automatically triggered.",
                "required": False
            },
            "default_mappging_mode": {
                "title": "Default to mapping mode",
                "type": "bool",
                "expected": bool,
                "default": True,
                "summary": "",
                "required": False
            },
            "switch_setenforce": {
                "title": "Patch SELinux",
                "type": "bool",
                "expected": bool,
                "default": False,
                "summary": "Patches very few SELinux rules, require for Samsung Stock ROMs for example (generally "
                           "enforcing kernels)",
                "required": False
            },
            "full_daemon": {
                "title": "Full daemon mode",
                "type": "bool",
                "expected": bool,
                "default": True,
                "summary": "Automatically start app on boot (and watchdog if enabled)",
                "required": False
            },
            "boot_delay": {
                "title": "Start Pogodroid with a delay (seconds)",
                "type": int,
                "expected": int,
                "default": 30,
                "summary": "",
                "required": False
            },
            "switch_enable_oomadj": {
                "title": "Override OOM value",
                "type": "bool",
                "expected": bool,
                "default": True,
                "summary": "Enables OOM adjustments to reduce the 'risk' of Android killing the app.",
                "required": False
            },
            "switch_enable_mock_location_patch": {
                "title": "Make mock location providers useful",
                "type": "bool",
                "expected": bool,
                "default": False,
                "summary": "Test feature: Mock location patching",
                "required": False
            }
        }
    }

    async def load_config(self) -> NoReturn:
        await super().load_config()
        if self.contents['post_destination'] in ['http://', '']:
            self.contents['post_destination'] = 'http://{}:{}'.format(self._args.mitmreceiver_ip,
                                                                      self._args.mitmreceiver_port)
        auths: List[SettingsAuth] = await SettingsAuthHelper.get_all(session, self._db.instance_id)
        if len(auths) > 0:
            self.sections['External Communication']['mad_auth']['required'] = True
