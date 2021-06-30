from mapadroid.mitm_receiver.endpoints.AbstractMitmReceiverRootEndpoint import AbstractMitmReceiverRootEndpoint


class StatusEndpoint(AbstractMitmReceiverRootEndpoint):
    """
    "/status"
    """

    # TODO: Auth
    async def get(self):
        self._check_mitm_status_auth()

        origin_return: dict = {}
        data_return: dict = {}
        for origin in (await self._get_mapping_manager().get_all_devicemappings()).keys():
            origin_return[origin] = {}
            origin_return[origin]['injection_status'] = await self._get_mitm_mapper().get_injection_status(origin)
            origin_return[origin]['latest_data'] = await self._get_mitm_mapper().request_latest(origin,
                                                                                                'timestamp_last_data')
            origin_return[origin]['mode_value'] = await self._get_mitm_mapper().request_latest(origin,
                                                                                               'injected_settings')
            origin_return[origin][
                'last_possibly_moved'] = await self._get_mitm_mapper().get_last_timestamp_possible_moved(origin)

        data_return['origin_status'] = origin_return
        return self._json_response(data_return)
