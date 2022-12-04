from aiohttp import web

from mapadroid.madmin.endpoints.routes.misc.JobstatusEndpoint import \
    JobstatusEndpoint
from mapadroid.madmin.endpoints.routes.misc.PickWorkerEndpoint import \
    PickWorkerEndpoint
from mapadroid.madmin.endpoints.routes.misc.QuestsEndpoint import \
    QuestsEndpoint
from mapadroid.madmin.endpoints.routes.misc.QuestsPubEndpoint import \
    QuestsPubEndpoint
from mapadroid.madmin.endpoints.routes.misc.RobotsTxtEndpoint import \
    RobotsTxtEndpoint
from mapadroid.madmin.endpoints.routes.misc.ScreenshotEndpoint import \
    ScreenshotEndpoint


def register_routes_misc_endpoints(app: web.Application):
    app.router.add_view('/screenshot/{path}', ScreenshotEndpoint, name='pushscreens')
    # TODO: Make sure if needed
    #  app.router.add_view('/static/{path}', DevicecontrolEndpoint, name='pushstatic')
    app.router.add_view('/quests', QuestsEndpoint, name='quest')
    app.router.add_view('/quests_pub', QuestsPubEndpoint, name='quest_pub')
    app.router.add_view('/pick_worker', PickWorkerEndpoint, name='pickworker')
    app.router.add_view('/jobstatus', JobstatusEndpoint, name='jobstatus')
    app.router.add_view('/robots.txt', RobotsTxtEndpoint, name='send_static_file')
