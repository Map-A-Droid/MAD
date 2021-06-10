from typing import List, Optional

from mapadroid.db.helper.TrsS2CellHelper import TrsS2CellHelper
from mapadroid.db.model import TrsS2Cell
from mapadroid.madmin.AbstractRootEndpoint import AbstractRootEndpoint
from mapadroid.madmin.functions import get_bound_params
from mapadroid.utils.collections import Location
from mapadroid.utils.s2Helper import S2Helper


class GetCellsEndpoint(AbstractRootEndpoint):
    """
    "/get_cells"
    """

    # TODO: Auth
    async def get(self):
        ne_lat, ne_lng, sw_lat, sw_lng, o_ne_lat, o_ne_lng, o_sw_lat, o_sw_lng = get_bound_params(self._request)
        timestamp: Optional[int] = self._request.query.get("timestamp")
        if timestamp:
            timestamp = int(timestamp)
        data: List[TrsS2Cell] = \
            await TrsS2CellHelper.get_cells_in_rectangle(self._session,
                                                         ne_corner=Location(ne_lat, ne_lng),
                                                         sw_corner=Location(sw_lat, sw_lng),
                                                         old_ne_corner=Location(o_ne_lat, o_ne_lng),
                                                         old_sw_corner=Location(o_sw_lat, o_sw_lng),
                                                         timestamp=timestamp)

        ret = []
        for cell in data:
            ret.append({
                "id": cell.id,
                "polygon": S2Helper.coords_of_cell(cell.id),
                "updated": cell.updated
            })
        return self._json_response(ret)
