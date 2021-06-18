from aiohttp import web

from mapadroid.mitm_receiver.endpoints.autoconfig.AutoconfMymacEndpoint import AutoconfMymacEndpoint
from mapadroid.mitm_receiver.endpoints.autoconfig.AutoconfRegisterEndpoint import AutoconfRegisterEndpoint
from mapadroid.mitm_receiver.endpoints.autoconfig.AutoconfStatusOperationEndpoint import AutoconfStatusOperationEndpoint
from mapadroid.mitm_receiver.endpoints.autoconfig.OriginGeneratorEndpoint import OriginGeneratorEndpoint


def register_autoconfig_endpoints(app: web.Application):
    app.router.add_view('/autoconfig/register', AutoconfRegisterEndpoint, name='autoconfig_register')
    app.router.add_view('/autoconfig/mymac', AutoconfMymacEndpoint, name='autoconfig_mymac')
    app.router.add_view('/autoconfig/{session_id}/{operation}', AutoconfStatusOperationEndpoint,
                        name='autoconfig_status_operation')
    app.router.add_view('/origin_generator', OriginGeneratorEndpoint, name='origin_generator')

