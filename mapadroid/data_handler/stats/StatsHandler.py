import time
from typing import Dict

from mapadroid.data_handler.stats.PlayerStats import PlayerStats
from mapadroid.db.DbWrapper import DbWrapper
from mapadroid.db.helper.TrsStatsLocationRawHelper import TrsStatsLocationRawHelper


class StatsHandler:
    """
    Class to handle all kinds of stats and the submission towards DB thereof
    """

    def __init__(self, db_wrapper: DbWrapper):
        self.__db_wrapper = db_wrapper
        self.__worker_stats: Dict[str, PlayerStats] = {}


    # TODO: Task with 5min timer calling
    #                      await self.__run_stats_processing(client_id, last_processed_timestamp, stats)
    async def __run_stats_processing(self, client_id, last_processed_timestamp, stats):
        logger.info("Running stats processing on {}", client_id)
        async with self.__db_wrapper as session, session:
            await self.__process_stats(session, stats, client_id, last_processed_timestamp)
            try:
                await session.commit()
            except Exception as e:
                logger.exception(e)
                await session.rollback()

    async def __process_stats(self, session: AsyncSession, stats_by_origin: Dict[str, Dict], last_processed_timestamp: float):
        logger.debug('Submitting stats')
        for origin, stats in stats_by_origin.items():
            data_send_stats = PlayerStats.stats_complete_parser(origin, stats, last_processed_timestamp)
            data_send_location = PlayerStats.stats_location_parser(origin, stats, last_processed_timestamp)

            await TrsStatsDetectHelper.add(session, *data_send_stats)
            await TrsStatsLocationHelper.add(session, *data_send_location)
            if self.__application_args.game_stats_raw:
                data_send_location_raw: List = PlayerStats.stats_location_raw_parser(origin, stats,
                                                                                     last_processed_timestamp)
                data_send_detection_raw: List = PlayerStats.stats_detection_raw_parser(origin, stats,
                                                                                       last_processed_timestamp)
                for raw_location_data in data_send_location_raw:
                    await TrsStatsLocationRawHelper.add(session, *raw_location_data)
                raw_mons_data = [mon for mon in data_send_detection_raw if (mon[2] in ['mon', 'mon_iv'])]
                for raw_mon_data in raw_mons_data:
                    await TrsStatsDetectMonRawHelper.add(session, *raw_mon_data)


        await self.__cleanup_stats(session)

    async def __cleanup_stats(self, session: AsyncSession) -> None:
        delete_before_timestamp: int = int(time.time()) - 604800
        await TrsStatsDetectHelper.cleanup(session, delete_before_timestamp)
        await TrsStatsDetectMonRawHelper.cleanup(session, delete_before_timestamp,
                                                 raw_delete_shiny_days=self.__application_args.raw_delete_shiny)
        await TrsStatsDetectFortRawHelper.cleanup(session, delete_before_timestamp)
        await TrsStatsLocationHelper.cleanup(session, delete_before_timestamp)
        await TrsStatsLocationRawHelper.cleanup(session, delete_before_timestamp)
