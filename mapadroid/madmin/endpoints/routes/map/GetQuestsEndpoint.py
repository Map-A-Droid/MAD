from typing import Optional, Dict, Tuple

from mapadroid.db.helper.PokestopHelper import PokestopHelper
from mapadroid.db.model import Pokestop, TrsQuest
from mapadroid.madmin.AbstractRootEndpoint import AbstractRootEndpoint
from mapadroid.madmin.functions import get_bound_params, generate_coords_from_geofence
from mapadroid.utils.collections import Location
from mapadroid.utils.questGen import generate_quest


class GetQuestsEndpoint(AbstractRootEndpoint):
    """
    "/get_quests"
    """

    # TODO: Auth
    async def get(self):
        quests = []

        fence = self._request.query.get("fence")
        if fence not in (None, 'None', 'All'):
            fence = generate_coords_from_geofence(self._get_mapping_manager(), self._session, self._get_instance_id(),
                                                  fence)
        else:
            fence = None
        ne_lat, ne_lng, sw_lat, sw_lng, o_ne_lat, o_ne_lng, o_sw_lat, o_sw_lng = get_bound_params(self._request)
        timestamp: Optional[int] = self._request.query.get("timestamp")
        if timestamp:
            timestamp = int(timestamp)
        data: Dict[int, Tuple[Pokestop, TrsQuest]] = \
            await PokestopHelper.get_with_quests(self._session,
                                                 ne_corner=Location(ne_lat, ne_lng),
                                                 sw_corner=Location(sw_lat, sw_lng),
                                                 old_ne_corner=Location(o_ne_lat, o_ne_lng),
                                                 old_sw_corner=Location(o_sw_lat, o_sw_lng),
                                                 timestamp=timestamp,
                                                 fence=fence)

        # questinfo = {}
        # for pokestop_id, (pokestop, quest) in data.items():
        #     mon = "%03d" % quest.quest_pokemon_id
        #     form_id = "%02d" % quest.quest_pokemon_form_id
        #     costume_id = "%02d" % quest.quest_pokemon_costume_id
        #     questinfo[pokestop_id] = ({
        #         'pokestop_id': pokestop_id, 'latitude': pokestop.latitude, 'longitude': pokestop.longitude,
        #         'quest_type': quest.quest_type, 'quest_stardust': quest.quest_stardust,
        #         'quest_pokemon_id': mon, 'quest_pokemon_form_id': form_id,
        #         'quest_pokemon_costume_id': costume_id,
        #         'quest_reward_type': quest.quest_reward_type, 'quest_item_id': quest.quest_item_id,
        #         'quest_item_amount': quest.quest_item_amount, 'name': pokestop.name, 'image': pokestop.image,
        #         'quest_target': quest.quest_target,
        #         'quest_condition': quest.quest_condition, 'quest_timestamp': quest.quest_timestamp,
        #         'task': quest.quest_task, 'quest_reward': quest.quest_reward, 'quest_template': quest.quest_template,
        #         'is_ar_scan_eligible': pokestop.is_ar_scan_eligible
        #     })

        for stop_id, (stop, quest) in data.items():
            quests.append(await generate_quest(stop, quest))

        return self._json_response(quests)
