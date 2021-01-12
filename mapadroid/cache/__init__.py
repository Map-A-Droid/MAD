from mapadroid.cache.noopcache import NoopCache
from mapadroid.utils.logging import LoggerEnums, get_logger

logger = get_logger(LoggerEnums.system)


def get_cache(args):
    cache = NoopCache()
    if args.enable_cache:
        try:
            import redis
            cache = redis.Redis(host=args.cache_host, port=args.cache_port, db=args.cache_database)
            cache.ping()
        except ImportError:
            logger.error("Cache enabled but redis dependency not installed. Continuing without cache")
        except redis.exceptions.ConnectionError:
            logger.error("Unable to connect to Redis server. Continouing without cache")
        except Exception:
            logger.error("Unknown error while enabling cache. Continuing without cache")

    return cache
