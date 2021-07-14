import time

from mapadroid.utils.collections import Location
from loguru import logger


class MitmDataHandler:
    """
    Class storing the last received proto of an origin and other relevant data that has to be available asap
    """

    async def request_latest(self, origin, key=None):
        logger.debug2("Request latest called")
        result = None
        retrieved = self.__mapping.get(origin, None)
        if key is None:
            result = retrieved
        elif retrieved is not None:
            result = retrieved.get(key, None)
        logger.debug2("Request latest done")
        return result

    # origin, method, data, timestamp
    async def update_latest(self, origin: str, key: str, values_dict, timestamp_received_raw: float = None,
                            timestamp_received_receiver: float = None, location: Location = None):
        if timestamp_received_raw is None:
            timestamp_received_raw = time.time()

        if timestamp_received_receiver is None:
            timestamp_received_receiver = time.time()

        updated = False
        if origin in self.__mapping:
            logger.debug2("Updating timestamp at {} with method {} to {}", location, key,
                                 timestamp_received_raw)
            if self.__mapping.get(origin) is not None and self.__mapping[origin].get(key) is not None:
                del self.__mapping[origin][key]
            self.__mapping[origin][key] = {}
            if location is not None:
                self.__mapping[origin]["location"] = location
            if timestamp_received_raw is not None:
                self.__mapping[origin][key]["timestamp"] = timestamp_received_raw
                self.__mapping[origin]["timestamp_last_data"] = timestamp_received_raw
            if timestamp_received_receiver is not None:
                self.__mapping[origin]["timestamp_receiver"] = timestamp_received_receiver
            self.__mapping[origin][key]["values"] = values_dict
            updated = True
        else:
            logger.warning("Not updating timestamp since origin is unknown")
        logger.debug2("Done updating proto {}", key)
        return updated

    # TODO: Call it from within update_latest accordingly rather than externally...
    def submit_gmo_for_location(self, origin, payload):
        cells = payload.get("cells", None)

        if cells is None:
            return

        current_cells_id = sorted(list(map(lambda x: x['id'], cells)))
        if origin in self.__last_cellsid:
            last_cells_id = self.__last_cellsid[origin]
            self.__last_cellsid[origin] = current_cells_id
            if last_cells_id != current_cells_id:
                self.__last_possibly_moved[origin] = time.time()
        else:
            self.__last_cellsid[origin] = current_cells_id
            self.__last_possibly_moved[origin] = time.time()
        logger.debug4("Done submit_gmo_for_location with {}", current_cells_id)

    def get_last_timestamp_possible_moved(self, origin):
        return self.__last_possibly_moved.get(origin, None)
