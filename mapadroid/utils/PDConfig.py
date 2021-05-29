from typing import List

from mapadroid.db.helper.SettingsAuthHelper import SettingsAuthHelper
from mapadroid.db.model import SettingsAuth
from mapadroid.utils.autoconfig import AutoConfigCreator


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

    async def load_config(self) -> None:
        await super().load_config()
        if self.contents['post_destination'] in ['http://', '']:
            self.contents['post_destination'] = 'http://{}:{}'.format(self._args.mitmreceiver_ip,
                                                                      self._args.mitmreceiver_port)
        auths: List[SettingsAuth] = await SettingsAuthHelper.get_all(self._session, self._instance_id)
        if len(auths) > 0:
            self.sections['External Communication']['mad_auth']['required'] = True
