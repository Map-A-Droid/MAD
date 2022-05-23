from typing import Optional
from yarl import URL

from aiohttp_remotes.exceptions import TooManyHeaders

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
    if not prefix:
        return url
    else:
        return URL(prefix).join(url)
