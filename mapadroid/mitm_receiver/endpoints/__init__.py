from aiohttp import web

from mapadroid.mitm_receiver.endpoints.GetAddressesEndpoint import GetAddressesEndpoint
from mapadroid.mitm_receiver.endpoints.GetLatestEndpoint import GetLatestEndpoint
from mapadroid.mitm_receiver.endpoints.ReceiveProtosEndpoint import ReceiveProtosEndpoint


def register_mitm_receiver_root_endpoints(app: web.Application):
    app.router.add_view('/get_addresses', GetAddressesEndpoint, name='get_addresses')
    app.router.add_view('/', ReceiveProtosEndpoint, name='receive_protos')
    app.router.add_view('/get_latest_mitm', GetLatestEndpoint, name='get_latest_mitm')
