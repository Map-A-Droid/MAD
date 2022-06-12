from aiohttp import web
from aiohttp_remotes.exceptions import RemoteError
from aiohttp_remotes.x_forwarded import XForwardedBase
from yarl import URL

from mapadroid.utils.aiohttp import X_FORWARDED_PATH, get_forwarded_path
from mapadroid.utils.logging import LoggerEnums, get_logger

logger = get_logger(LoggerEnums.system)


# Inspired by https://github.com/spec-first/connexion/pull/823/files#diff-b645bcdf51da7a8df4623c977c52d9a57139935c407a4024c211dce4893c92abR16
class XPathForwarded(XForwardedBase):

    def __init__(self, num=1):
        logger.warning("{} enabled", self.__class__.__name__)
        self._num = num

    @web.middleware
    async def middleware(self, request, handler):
        logger.debug2("Using middleware to read header {} of request to {}.",
                      X_FORWARDED_PATH, request.path)
        try:
            overrides = {}
            headers = request.headers

            forwarded_for = self.get_forwarded_for(headers)
            if forwarded_for:
                overrides['remote'] = str(forwarded_for[-self._num])

            proto = self.get_forwarded_proto(headers)
            if proto:
                overrides['scheme'] = proto[-self._num]

            host = self.get_forwarded_host(headers)
            if host is not None:
                overrides['host'] = host
            request_path = None
            prefix = get_forwarded_path(headers)
            if prefix is not None:
                prefix = '/' + prefix.strip('/') + '/'
                request_path = URL(request.path_qs.lstrip('/'))
                overrides['rel_url'] = URL(prefix).join(request_path)

            request = request.clone(**overrides)
            logger.debug2("Handling request to {} ({})", request.path, request_path)
            return await handler(request)
        except RemoteError as exc:
            exc.log(request)
        await self.raise_error(request)
