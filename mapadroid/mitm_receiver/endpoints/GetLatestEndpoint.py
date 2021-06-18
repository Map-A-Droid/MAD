from loguru import logger

from mapadroid.mitm_receiver.endpoints.AbstractMitmReceiverRootEndpoint import AbstractMitmReceiverRootEndpoint


class GetLatestEndpoint(AbstractMitmReceiverRootEndpoint):
    """
    "/get_latest_mitm"
    """

    # TODO: Check Origin etc auth checks using decorators or better: visitor pattern...

    async def _iter(self):
        # TODO: VisitorPattern for extra auth checks...
        with logger.contextualize(ip=self._get_request_address(), name="endpoint"):
            await self._check_origin_header()
            return await super()._iter()

    async def get(self):
        origin = self.request.headers.get("Origin")
        injected_settings = await self._get_mitm_mapper().request_latest(
            origin, "injected_settings")

        ids_iv = await self._get_mitm_mapper().request_latest(origin, "ids_iv")
        if ids_iv is not None:
            ids_iv = ids_iv.get("values", None)

        safe_items = await self._get_mitm_mapper().get_safe_items(origin)
        level_mode = await self._get_mitm_mapper().get_levelmode(origin)

        ids_encountered = await self._get_mitm_mapper().request_latest(
            origin, "ids_encountered")
        if ids_encountered is not None:
            ids_encountered = ids_encountered.get("values", None)

        unquest_stops = await self._get_mitm_mapper().request_latest(
            origin, "unquest_stops")
        if unquest_stops is not None:
            unquest_stops = unquest_stops.get("values", [])

        response = {"ids_iv": ids_iv, "injected_settings": injected_settings,
                    "ids_encountered": ids_encountered, "safe_items": safe_items,
                    "lvl_mode": level_mode, 'unquest_stops': unquest_stops}
        return self._json_response(response)
