import asyncio

from mapadroid.utils.logging import get_logger, LoggerEnums
from mapadroid.utils.madGlobals import application_args, terminate_mad

logger = get_logger(LoggerEnums.system)

async def report_queue_size(__db_wrapper, __queueObject):
    __cache_key = application_args.redis_report_queue_key
    __sleep_time = application_args.redis_report_queue_interval
    logger.info("Reporting queue size to redis via key {} starting", __cache_key)
    while not terminate_mad.is_set():
        logger.info('Reporting queue size to redis while not starting')
        __cache: Redis = await __db_wrapper.get_cache()
        __value = __queueObject.qsize()
        logger.info('Reporting queue size to redis while not value: {}', __value)
        await __cache.set(__cache_key, __value, ex=__sleep_time*2)
        logger.info('Reporting queue size to redis sleeping for: {}', __sleep_time)
        await asyncio.sleep(__sleep_time)

