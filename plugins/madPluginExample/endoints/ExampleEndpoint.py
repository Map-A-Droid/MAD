from mapadroid.plugins.endpoints.AbstractPluginEndpoint import AbstractPluginEndpoint
import aiohttp_jinja2


class ExampleEndpoint(AbstractPluginEndpoint):
    """
    "/example"
    """

    # TODO: Auth
    @aiohttp_jinja2.template('testfile.html')
    async def get(self):
        return {"header": "Test Plugin",
                "title": "Test Plugin"}
