from aiohttp import web

def register_api_endpoints(app: web.Application):
    app.router.add_view('/account/login', Login)