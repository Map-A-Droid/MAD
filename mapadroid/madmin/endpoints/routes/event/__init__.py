from aiohttp import web

from mapadroid.madmin.endpoints.routes.event.DeleteEventEndpoint import DeleteEventEndpoint
from mapadroid.madmin.endpoints.routes.event.EditEventEndpoint import EditEventEndpoint
from mapadroid.madmin.endpoints.routes.event.EventsEndpoint import EventsEndpoint
from mapadroid.madmin.endpoints.routes.event.GetEventsEndpoint import GetEventsEndpoint
from mapadroid.madmin.endpoints.routes.event.SaveEventEndpoint import SaveEventEndpoint


def register_routes_event_endpoints(app: web.Application):
    app.router.add_view('/events', EventsEndpoint, name='events')
    app.router.add_view('/get_events', GetEventsEndpoint, name='get_events')
    app.router.add_view('/edit_event', EditEventEndpoint, name='edit_event')
    app.router.add_view('/save_event', SaveEventEndpoint, name='save_event')
    app.router.add_view('/del_event', DeleteEventEndpoint, name='del_event')
