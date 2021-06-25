from mapadroid.plugins.endpoints.AbstractPluginEndpoint import AbstractPluginEndpoint
import aiohttp_jinja2


class PluginfaqEndpoint(AbstractPluginEndpoint):
    """
    "/pluginfaq"
    """

    # TODO: Auth
    @aiohttp_jinja2.template('pluginfaq.html')
    async def get(self):
        return {"header": "Test Plugin",
                "title": "Test Plugin - FAQ"}
