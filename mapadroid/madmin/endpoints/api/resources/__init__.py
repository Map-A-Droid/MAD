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
    app.router.add_view('/api/area', AreaEndpoint)
    app.router.add_view('/api/area/{identifier}', AreaEndpoint)

    app.router.add_view('/api/auth', AuthEndpoint)
    app.router.add_view('/api/auth/{identifier}', AuthEndpoint)

    app.router.add_view('/api/device', DeviceEndpoint)
    app.router.add_view('/api/device/{identifier}', DeviceEndpoint)

    app.router.add_view('/api/devicepool', DevicepoolEndpoint)
    app.router.add_view('/api/devicepool/{identifier}', DevicepoolEndpoint)

    app.router.add_view('/api/geofence', GeofenceEndpoint)
    app.router.add_view('/api/geofence/{identifier}', GeofenceEndpoint)

    app.router.add_view('/api/monivlist', MonIvListEndpoint)
    app.router.add_view('/api/monivlist/{identifier}', MonIvListEndpoint)

    app.router.add_view('/api/pogoauth', PogoauthEndpoint)
    app.router.add_view('/api/pogoauth/{identifier}', PogoauthEndpoint)

    app.router.add_view('/api/routecalc', RoutecalcEndpoint)
    app.router.add_view('/api/routecalc/{identifier}', RoutecalcEndpoint)

    app.router.add_view('/api/walker', WalkerEndpoint)
    app.router.add_view('/api/walker/{identifier}', WalkerEndpoint)

    app.router.add_view('/api/walkerarea', WalkerareaEndpoint)
    app.router.add_view('/api/walkerarea/{identifier}', WalkerareaEndpoint)
