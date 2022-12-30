from typing import List, Optional

from loguru import logger

from mapadroid.data_handler.mitm_data.holder.latest_mitm_data.LatestMitmDataEntry import \
    LatestMitmDataEntry
from mapadroid.mitm_receiver.endpoints.AbstractMitmReceiverRootEndpoint import \
    AbstractMitmReceiverRootEndpoint


class GetLatestEndpoint(AbstractMitmReceiverRootEndpoint):
    """
    "/get_latest_mitm"
    """

    # TODO: Check Origin etc auth checks using decorators or better: visitor pattern...

    async def _iter(self):
        # TODO: VisitorPattern for extra auth checks...
        with logger.contextualize(identifier=self._get_request_address(), name="get_latest-endpoint"):
            await self._check_origin_header()
            return await super()._iter()

    async def get(self):
        origin = self.request.headers.get("Origin")
        injected_settings_entry: Optional[LatestMitmDataEntry] = await self._get_mitm_mapper().request_latest(
            origin, "injected_settings")
        injected_settings = injected_settings_entry.data if injected_settings_entry and injected_settings_entry.data else None
        # Workaround for PD...
        injected_settings_dict = {"values": injected_settings}

        ids_iv_entry: Optional[LatestMitmDataEntry] = await self._get_mitm_mapper().request_latest(origin, "ids_iv")
        ids_iv = []
        if ids_iv_entry and ids_iv_entry.data:
            for id_iv in ids_iv_entry.data:
                ids_iv.append(int(id_iv))

        safe_items = await self._get_mapping_manager().get_safe_items(origin)
        level_mode = await self._get_mapping_manager().routemanager_of_origin_is_levelmode(origin)
        quest_layer_to_scan: int = await self._get_mapping_manager().routemanager_get_quest_layer_to_scan_of_origin(origin)

        ids_encountered_entry: Optional[LatestMitmDataEntry] = await self._get_mitm_mapper().request_latest(
            origin, "ids_encountered")
        ids_encountered = None
        if ids_encountered_entry is not None:
            ids_encountered = ids_encountered_entry.data

        unquest_stops_res: List[str] = []
        unquest_stops: Optional[LatestMitmDataEntry] = await self._get_mitm_mapper().request_latest(
            origin, "unquest_stops")
        if unquest_stops and unquest_stops.data:
            unquest_stops_res: List[str] = unquest_stops.data

        response = {"ids_iv": ids_iv, "injected_settings": injected_settings_dict,
                    "ids_encountered": ids_encountered, "safe_items": safe_items,
                    "lvl_mode": level_mode, 'unquest_stops': unquest_stops_res,
                    "check_lured": self._get_mad_args().scan_lured_mons,
                    "quest_layer_scan": quest_layer_to_scan}
        return self._json_response(response)
