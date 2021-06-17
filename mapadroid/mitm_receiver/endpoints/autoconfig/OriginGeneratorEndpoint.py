from mapadroid.mitm_receiver.endpoints.AbstractDeviceAuthEndpoint import AbstractDeviceAuthEndpoint
from mapadroid.mitm_receiver.endpoints.AbstractMitmReceiverRootEndpoint import AbstractMitmReceiverRootEndpoint
from mapadroid.utils.autoconfig import origin_generator


class OriginGeneratorEndpoint(AbstractMitmReceiverRootEndpoint):
    """
    "/origin_generator"
    """

    # TODO: Auth/preprocessing for autoconfig?
    async def get(self):
        body = await self.request.json()
        return await origin_generator(self._session, self._get_instance_id(), **body)
