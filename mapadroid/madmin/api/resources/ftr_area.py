from typing import Optional

from mapadroid.db.helper import SettingsRoutecalcHelper
from mapadroid.db.helper.SettingsAreaHelper import SettingsAreaHelper
from mapadroid.db.model import SettingsArea, SettingsRoutecalc
from mapadroid.madmin.api.resources.resource_exceptions import NoModeSpecified

from .resourceHandler import ResourceHandler


class APIArea(ResourceHandler):
    component = 'area'
    default_sort = 'name'
    description = 'Add/Update/Delete Areas used for Walkers'
    has_rpc_calls = True

    def get_resource_info(self, resource_def):
        if self.mode is None:
            return 'Please specify a mode for resource information.  Valid modes: %s' % (
                ','.join(self.configuration.keys()))
        else:
            return super().get_resource_info(resource_def)

    def post(self, identifier, data, resource_def, resource_info, *args, **kwargs):
        if self.api_req.content_type == 'application/json-rpc':
            try:
                call = self.api_req.data['call']
                args = self.api_req.data.get('args', {})
                if call == 'recalculate':
                    area: Optional[SettingsArea] = await self._db_wrapper.get_area(session, identifier)
                    if not area:
                        return 'Unable to recalc, area not found', 422
                    routecalc_id: Optional[int] = getattr(area, "routecalc", None)
                    # iv_mitm is PrioQ driven and idle does not have a route.  This are not recalcable and the returned
                    # status should be representative of that
                    if area.mode in ['iv_mitm', 'idle']:
                        return ('Unable to recalc mode %s' % (area.mode,), 422)
                    routecalc: Optional[SettingsRoutecalc] = None
                    if routecalc_id:
                        routecalc: Optional[SettingsRoutecalc] = await SettingsRoutecalcHelper.get(session, instance_id, routecalc_id)
                    if routecalc and routecalc.recalc_status == 0:
                        # Start the recalculation.  This can take a little bit if the routemanager needs to be started
                        status = self._mapping_manager.routemanager_recalcualte(area.area_id)
                        if status:
                            return None, 204
                        else:
                            # Unable to turn on the routemanager.  Probably should use another error code
                            return None, 409
                    else:
                        # Do not allow another recalculation if one is already running.  This value is reset on startup
                        # so it will not be stuck in this state
                        return 'Recalc is already running on this Area', 422
                else:
                    # RPC not implemented
                    return call, 501
            except KeyError:
                return call, 501
        else:
            return super().post(identifier, data, resource_def, resource_info, *args, **kwargs)

    async def populate_mode(self, identifier, method):
        self.mode = self.api_req.headers.get('X-Mode', None)
        if self.mode is None:
            self.mode = self.api_req.params.get('mode', None)
        if self.mode:
            return
        if method in ['GET', 'PATCH']:
            if identifier is not None:
                area: Optional[SettingsArea] = await SettingsAreaHelper.get(session, instance_id, identifier)
                if area:
                    self.mode = area.mode
        elif method == 'POST':
            if self.api_req.content_type != 'application/json-rpc':
                raise NoModeSpecified()
        elif method == 'PUT':
            raise NoModeSpecified()
