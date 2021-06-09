from aiohttp import web

from mapadroid.madmin.endpoints.routes.map.GeoGeofencesEndpoint import GetGeofencesEndpoint
from mapadroid.madmin.endpoints.routes.map.GetAreasEndpoint import GetAreasEndpoint
from mapadroid.madmin.endpoints.routes.map.GetCellsEndpoint import GetCellsEndpoint
from mapadroid.madmin.endpoints.routes.map.GetGymcoords import GetGymcoordsEndpoint
from mapadroid.madmin.endpoints.routes.map.GetMapMonsEndpoint import GetMapMonsEndpoint
from mapadroid.madmin.endpoints.routes.map.GetPriorouteEndpoint import GetPriorouteEndpoint
from mapadroid.madmin.endpoints.routes.map.GetQuestsEndpoint import GetQuestsEndpoint
from mapadroid.madmin.endpoints.routes.map.GetRouteEndpoint import GetRouteEndpoint
from mapadroid.madmin.endpoints.routes.map.GetSpawnsEndpoint import GetSpawnsEndpoint
from mapadroid.madmin.endpoints.routes.map.GetStopsEndpoint import GetStopsEndpoint
from mapadroid.madmin.endpoints.routes.map.GetWorkersEndpoint import GetWorkersEndpoint
from mapadroid.madmin.endpoints.routes.map.MapEndpoint import MapEndpoint
from mapadroid.madmin.endpoints.routes.map.SaveFenceEndpoint import SaveFenceEndpoint


def register_routes_map_endpoints(app: web.Application):
    app.router.add_view('/map', MapEndpoint, name='map')
    app.router.add_view('/get_workers', GetWorkersEndpoint, name='get_workers')
    app.router.add_view('/get_geofences', GetGeofencesEndpoint, name='get_geofences')
    app.router.add_view('/get_areas', GetAreasEndpoint, name='get_areas')
    app.router.add_view('/get_route', GetRouteEndpoint, name='get_route')
    app.router.add_view('/get_prioroute', GetPriorouteEndpoint, name='get_prioroute')
    app.router.add_view('/get_spawns', GetSpawnsEndpoint, name='get_spawns')
    app.router.add_view('/get_gymcoords', GetGymcoordsEndpoint, name='get_gymcoords')
    app.router.add_view('/get_quests', GetQuestsEndpoint, name='get_quests')
    app.router.add_view('/get_map_mons', GetMapMonsEndpoint, name='get_map_mons')
    app.router.add_view('/get_cells', GetCellsEndpoint, name='get_cells')
    app.router.add_view('/get_stops', GetStopsEndpoint, name='get_stops')
    app.router.add_view('/savefence', SaveFenceEndpoint, name='savefence')
