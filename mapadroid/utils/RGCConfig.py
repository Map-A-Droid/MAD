from typing import List

from mapadroid.db.helper.SettingsAuthHelper import SettingsAuthHelper
from mapadroid.db.model import SettingsAuth
from mapadroid.utils.autoconfig import AutoConfigCreator


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

    async def load_config(self) -> None:
        await super().load_config()
        if self.contents['websocket_uri'] in ['ws://', '']:
            self.contents['websocket_uri'] = 'ws://{}:{}'.format(self._args.ws_ip, self._args.ws_port)
        auths: List[SettingsAuth] = await SettingsAuthHelper.get_all(self._session, self._instance_id)
        if len(auths) > 0:
            self.sections['Socket']['mad_auth']['required'] = True
