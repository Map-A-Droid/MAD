from aiohttp import web

from mapadroid.madmin.endpoints.routes.settings.RecalcStatusEndpoint import RecalcStatusEndpoint
from mapadroid.madmin.endpoints.routes.settings.ReloadEndpoint import ReloadEndpoint
from mapadroid.madmin.endpoints.routes.settings.SettingsAreasEndpoint import SettingsAreasEndpoint
from mapadroid.madmin.endpoints.routes.settings.SettingsAuthEndpoint import SettingsAuthEndpoint
from mapadroid.madmin.endpoints.routes.settings.SettingsDevicesEndpoint import SettingsDevicesEndpoint
from mapadroid.madmin.endpoints.routes.settings.SettingsEndpoint import SettingsEndpoint
from mapadroid.madmin.endpoints.routes.settings.SettingsGeofencesEndpoint import SettingsGeofenceEndpoint
from mapadroid.madmin.endpoints.routes.settings.SettingsIvlistsEndpoint import SettingsIvlistsEndpoint
from mapadroid.madmin.endpoints.routes.settings.SettingsMonsearchEndpoint import SettingsMonsearchEndpoint
from mapadroid.madmin.endpoints.routes.settings.SettingsPogoauthEndpoint import SettingsPogoauthEndpoint
from mapadroid.madmin.endpoints.routes.settings.SettingsPoolEndpoint import SettingsPoolEndpoint
from mapadroid.madmin.endpoints.routes.settings.SettingsRoutecalcEndpoint import SettingsRoutecalcEndpoint
from mapadroid.madmin.endpoints.routes.settings.SettingsWalkerAreaEndpoint import SettingsWalkerAreaEndpoint
from mapadroid.madmin.endpoints.routes.settings.SettingsWalkerEndpoint import SettingsWalkerEndpoint


def register_routes_settings_endpoints(app: web.Application):
    app.router.add_view('/settings', SettingsEndpoint, name='settings')
    app.router.add_view('/settings/areas', SettingsAreasEndpoint, name='settings_areas')
    app.router.add_view('/settings/auth', SettingsAuthEndpoint, name='settings_auth')
    app.router.add_view('/settings/devices', SettingsDevicesEndpoint, name='settings_devices')
    app.router.add_view('/settings/geofence', SettingsGeofenceEndpoint, name='settings_geofence')
    app.router.add_view('/settings/ivlists', SettingsIvlistsEndpoint, name='settings_ivlists')
    app.router.add_view('/settings/pogoauth', SettingsPogoauthEndpoint, name='settings_pogoauth')
    app.router.add_view('/settings/monsearch', SettingsMonsearchEndpoint, name='monsearch')
    app.router.add_view('/settings/shared', SettingsPoolEndpoint, name='settings_pools')
    app.router.add_view('/settings/routecalc', SettingsRoutecalcEndpoint, name='settings_routecalc')
    app.router.add_view('/settings/walker', SettingsWalkerEndpoint, name='settings_walkers')
    app.router.add_view('/settings/walker/areaeditor', SettingsWalkerAreaEndpoint, name='settings_walker_area')
    app.router.add_view('/recalc_status', RecalcStatusEndpoint, name='recalc_status')
    app.router.add_view('/reload', ReloadEndpoint, name='reload')
