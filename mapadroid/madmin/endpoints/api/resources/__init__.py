from aiohttp import web

from mapadroid.madmin.endpoints.api.resources.AreaEndpoint import AreaEndpoint
from mapadroid.madmin.endpoints.api.resources.AuthEndpoint import AuthEndpoint
from mapadroid.madmin.endpoints.api.resources.DeviceEndpoint import DeviceEndpoint
from mapadroid.madmin.endpoints.api.resources.DevicepoolEndpoint import DevicepoolEndpoint
from mapadroid.madmin.endpoints.api.resources.GeofenceEndpoint import GeofenceEndpoint
from mapadroid.madmin.endpoints.api.resources.MonIvListEndpoint import MonIvListEndpoint
from mapadroid.madmin.endpoints.api.resources.PogoauthEndpoint import PogoauthEndpoint
from mapadroid.madmin.endpoints.api.resources.RoutecalcEndpoint import RoutecalcEndpoint
from mapadroid.madmin.endpoints.api.resources.WalkerEndpoint import WalkerEndpoint
from mapadroid.madmin.endpoints.api.resources.WalkerareaEndpoint import WalkerareaEndpoint


def register_api_resources_endpoints(app: web.Application):
    app.router.add_view('/api/area', AreaEndpoint, name='api_area')
    app.router.add_view('/api/area/{identifier}', AreaEndpoint, name='api_area_identifier')

    app.router.add_view('/api/auth', AuthEndpoint, name='api_auth')
    app.router.add_view('/api/auth/{identifier}', AuthEndpoint, name='api_auth_identifier')

    app.router.add_view('/api/device', DeviceEndpoint, name='api_device')
    app.router.add_view('/api/device/{identifier}', DeviceEndpoint, name='api_device_identifier')

    app.router.add_view('/api/devicepool', DevicepoolEndpoint, name='api_devicepool')
    app.router.add_view('/api/devicepool/{identifier}', DevicepoolEndpoint, name='api_devicepool_identifier')

    app.router.add_view('/api/geofence', GeofenceEndpoint, name='api_geofence')
    app.router.add_view('/api/geofence/{identifier}', GeofenceEndpoint, name='api_geofence_identifier')

    app.router.add_view('/api/monivlist', MonIvListEndpoint, name='api_monivlist')
    app.router.add_view('/api/monivlist/{identifier}', MonIvListEndpoint, name='api_monivlist_identifier')

    app.router.add_view('/api/pogoauth', PogoauthEndpoint, name='api_pogoauth')
    app.router.add_view('/api/pogoauth/{identifier}', PogoauthEndpoint, name='api_pogoauth_identifier')

    app.router.add_view('/api/routecalc', RoutecalcEndpoint, name='api_routecalc')
    app.router.add_view('/api/routecalc/{identifier}', RoutecalcEndpoint, name='api_routecalc_identifier')

    app.router.add_view('/api/walker', WalkerEndpoint, name='api_walker')
    app.router.add_view('/api/walker/{identifier}', WalkerEndpoint, name='api_walker_identifier')

    app.router.add_view('/api/walkerarea', WalkerareaEndpoint, name='api_walkerarea')
    app.router.add_view('/api/walkerarea/{identifier}', WalkerareaEndpoint, name='api_walkerarea_identifier')
