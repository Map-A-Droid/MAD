from typing import Optional
from urllib.parse import urljoin
from yarl import URL
from aiohttp_remotes.exceptions import TooManyHeaders
from mapadroid.utils.logging import LoggerEnums, get_logger

logger = get_logger(LoggerEnums.system)
X_FORWARDED_PATH = "X-Forwarded-Path"


def get_forwarded_path(headers):
    forwarded_host = headers.getall(X_FORWARDED_PATH, [])
    if len(forwarded_host) > 1:
        raise TooManyHeaders(X_FORWARDED_PATH)
    return forwarded_host[0] if forwarded_host else None


def prefix_url_with_forwarded_path(headers, url: URL) -> URL:
    forwarded_prefix: Optional[str] = get_forwarded_path(headers)
    return add_prefix_to_url(forwarded_prefix, url)


def add_prefix_to_url(prefix: Optional[str], url: URL) -> URL:
    logger.debug("Prefix to be prepended to {}: {}", url, prefix)
    if prefix is None or len(prefix) == 0:
        logger.warning("Invalid prefix")
        return url
    else:
        joined = urljoin(prefix, str(url))
        logger.warning("Prepending to {}: ", str(url), joined)
        return URL(joined)
