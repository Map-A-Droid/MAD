import requests
import time
from mapadroid.utils.logging import get_logger, LoggerEnums


logger = get_logger(LoggerEnums.utils)


class TokenDispenser(requests.Session):
    def __init__(self, host: str, retries: int = 3, sleep_timer: float = 1.0, timeout: float = 3.0):
        # Create the session
        super().__init__()
        self.host = host
        self.retries = retries
        self.sleep_timer = sleep_timer
        self.timeout = timeout
        self.email = None
        self.token = None
        self.setup()

    def prepare_request(self, request):
        """ Override the class function to create the URL with the URI and any other processing required """
        if request.url[0] == "/":
            request.url = request.url[1:]
        request.url = "%s/%s" % (self.host, request.url)
        return super().prepare_request(request)

    def send(self, request, **kwargs):
        """ Override the class function to handle retries and specific error codes """
        attempt = 0
        finished = False
        expected_code = 200
        if "expected_code" in kwargs:
            expected_code = kwargs['expected_code']
            del kwargs['expected_code']
        last_err = None
        if "timeout" not in kwargs or ("timeout" in kwargs and kwargs["timeout"] is None):
            kwargs["timeout"] = self.timeout
        while not finished and attempt < self.retries:
            try:
                req_result = super().send(request, **kwargs)
                if req_result.status_code == expected_code:
                    return req_result
                else:
                    logger.debug('Invalid status code returned: {}', req_result.status_code)
            except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as err:
                logger.warning(err)
                last_err = err
            except Exception as err:
                logger.warning("Unknown exception, {}", err)
                last_err = err
            attempt += 1
            if attempt < self.retries:
                time.sleep(self.sleep_timer)
        raise last_err

    def setup(self) -> bool:
        try:
            self.email = self.get('email').text
            if self.email is None:
                return False
            self.token = self.get('token/email/%s' % (self.email)).text
            if self.token is None:
                return False
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError):
            logger.debug('Unable to use token-dispenser {}', self.host)
            return False
        return True
