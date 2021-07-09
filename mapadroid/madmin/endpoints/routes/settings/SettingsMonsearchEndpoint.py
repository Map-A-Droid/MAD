import os
import re
from typing import Optional

from aiohttp.abc import Request

from mapadroid.madmin.AbstractMadminRootEndpoint import AbstractMadminRootEndpoint
from mapadroid.utils.language import open_json_file, i8ln


class SettingsMonsearchEndpoint(AbstractMadminRootEndpoint):
    """
    "/settings/monsearch"
    """

    def __init__(self, request: Request):
        super().__init__(request)

    # TODO: Auth
    async def get(self):
        search: Optional[str] = self.request.query.get("search")
        pokemon = []
        if search or (search and len(search) >= 3):
            all_pokemon = await self.get_pokemon()
            mon_search_compiled = re.compile('.*%s.*' % (re.escape(search)), re.IGNORECASE)
            mon_names = list(filter(mon_search_compiled.search, all_pokemon['locale'].keys()))
            for name in sorted(mon_names):
                mon_id = all_pokemon['locale'][name]
                pokemon.append({"mon_name": name, "mon_id": str(mon_id)})
        return await self._json_response(pokemon)

    async def get_pokemon(self):
        mondata = await open_json_file('pokemon')
        # Why o.O
        stripped_mondata = {}
        for mon_id in mondata:
            stripped_mondata[mondata[str(mon_id)]["name"]] = mon_id
            if os.environ['LANGUAGE'] != "en":
                try:
                    localized_name = await i8ln(mondata[str(mon_id)]["name"])
                    stripped_mondata[localized_name] = mon_id
                except KeyError:
                    pass
        return {
            'mondata': mondata,
            'locale': stripped_mondata
        }
