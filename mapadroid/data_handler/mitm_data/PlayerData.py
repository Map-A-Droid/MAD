class PlayerData:
    def __init__(self, origin: str, application_args):
        self._worker: str = origin
        self.__application_args = application_args
        self._level: int = 0
        self._poke_stop_visits: int = 0

    def set_level(self, level: int) -> None:
        if self._level != level:
            logger.info('set level {}', level)
            self._level = int(level)

    def get_level(self) -> int:
        return self._level

    def set_poke_stop_visits(self, visits: int) -> None:
        logger.debug2('set pokestops visited {}', visits)
        self._poke_stop_visits = visits

    def get_poke_stop_visits(self) -> int:
        return self._poke_stop_visits


    async def gen_player_stats(self, data: dict) -> None:
        if 'inventory_delta' not in data:
            logger.debug2('gen_player_stats cannot generate new stats')
            return
        stats = data['inventory_delta'].get("inventory_items", None)
        if len(stats) > 0:
            for data_inventory in stats:
                player_stats = data_inventory['inventory_item_data']['player_stats']
                player_level = player_stats['level']
                if int(player_level) > 0:
                    logger.debug2('{{gen_player_stats}} saving new playerstats')
                    self.set_level(int(player_level))
                    self.set_poke_stop_visits(int(player_stats['poke_stop_visits']))
                    # TODO: Write player level to DB (in SerializedMitmDataProcessor/MitmMapper?)
                    return