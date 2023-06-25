import asyncio

from redis.asyncio.client import Redis

from mapadroid.utils.logging import LoggerEnums, get_logger
from mapadroid.utils.madGlobals import MadGlobals, terminate_mad

logger = get_logger(LoggerEnums.system)


async def report_queue_size(__db_wrapper, __queueObject):
    __cache_key = MadGlobals.application_args.redis_report_queue_key
    __sleep_time = MadGlobals.application_args.redis_report_queue_interval
    while not terminate_mad.is_set():
        __cache: Redis = await __db_wrapper.get_cache()
        __value = __queueObject.qsize()
        await __cache.set(__cache_key, __value, ex=__sleep_time*2)
        await asyncio.sleep(__sleep_time)
