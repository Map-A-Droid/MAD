import asyncio
from typing import Optional

from aiohttp import web

from mapadroid.madmin.endpoints.routes.control.AbstractControlEndpoint import \
    AbstractControlEndpoint
from mapadroid.madmin.functions import generate_device_logcat_zip_path
from mapadroid.utils.collections import Location
from mapadroid.utils.functions import generate_path
from mapadroid.utils.MappingManager import DeviceMappingsEntry


class SendGpsEndpoint(AbstractControlEndpoint):
    """
    "/send_gps"
    """

    # TODO: Auth
    async def get(self):
        origin: Optional[str] = self.request.query.get("origin")
        # devicemappings: Optional[DeviceMappingsEntry] = await self._get_mapping_manager().get_devicemappings_of(origin)
        # origin_logger = get_origin_logger(self._logger, origin=origin)

        coords = self.request.query.get('coords').replace(' ', '').split(',')
        sleeptime = self.request.query.get('sleeptime', "0")
        if len(coords) < 2:
            return web.Response(text='Wrong Format!')
        # origin_logger.info('MADmin: Set GPS Coords {}, {} - WS Mode only!', coords[0], coords[1])
        try:
            temp_comm = self._get_ws_server().get_origin_communicator(origin)
            await temp_comm.set_location(Location(coords[0], coords[1]), 0)
            if int(sleeptime) > 0:
                # origin_logger.info("MADmin: Set additional sleeptime: {}", sleeptime)
                self._get_ws_server().set_geofix_sleeptime_worker(origin, int(sleeptime))
        except Exception as e:
            # origin_logger.exception('MADmin: Exception occurred while set gps coords: {}.', e)
            pass
            # TODO: Respond with error properly.

        await asyncio.sleep(2)
        creationdate = await self._take_screenshot()
        return web.Response(text=creationdate)
