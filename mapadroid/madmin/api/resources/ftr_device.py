from typing import Optional

from mapadroid.db.helper.SettingsDeviceHelper import SettingsDeviceHelper
from mapadroid.db.helper.TrsVisitedHelper import TrsVisitedHelper
from mapadroid.db.model import SettingsDevice

from .resourceHandler import ResourceHandler


class APIDevice(ResourceHandler):
    component = 'device'
    default_sort = 'origin'
    description = 'Add/Update/Delete device (Origin) settings'
    has_rpc_calls = True

    def post(self, identifier, data, resource_def, resource_info, *args, **kwargs):
        device: Optional[SettingsDevice] = await SettingsDeviceHelper.get(session, instance_id, identifier)
        if self.api_req.content_type == 'application/json-rpc':
            if not device:
                return "", 404
            call = self.api_req.data.get("call", None)
            args = self.api_req.data.get('args', {})
            if call == 'device_state':
                active = args.get('active', 1)
                self._mapping_manager.set_device_state(int(identifier), active)
                self._mapping_manager.device_set_disabled(device.name)
                self._ws_server.force_disconnect(device.name)
                return None, 200
            elif call == 'flush_level':
                await TrsVisitedHelper.flush_all_of_origin(session, device.name)
                return None, 204
            else:
                return call, 501
        else:
            # TODO: Super.post needs to be passed the type/class/existing instance?
            return super().post(identifier, data, resource_def, resource_info, *args, **kwargs)
