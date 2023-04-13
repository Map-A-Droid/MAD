import unittest
from typing import List

from mapadroid.route.routecalc.calculate_route_all import route_calc_all
from mapadroid.utils.collections import Location
from mapadroid.utils.madGlobals import RoutecalculationTypes


class TestRouteCalcAll(unittest.IsolatedAsyncioTestCase):
    async def test_route_calc_all(self):
        coords: List[Location] = []
        coords.append(Location(52.519903, 13.400699))
        coords.append(Location(52.526848, 13.392288))
        coords.append(Location(52.525230, 13.409111))
        coords.append(Location(52.518910, 13.420354))
        coords.append(Location(52.514836, 13.409282))
        await route_calc_all(coords, "foo", RoutecalculationTypes.OR_TOOLS)

        # self.fail()
