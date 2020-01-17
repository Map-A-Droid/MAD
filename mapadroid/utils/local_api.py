import time

import requests

from mapadroid.utils.walkerArgs import parseArgs

mapping_args = parseArgs()


class LocalAPI(requests.Session):
    def __init__(self, **kwargs):
        super(LocalAPI, self).__init__()
        self.__logger = kwargs.get('logger', None)
        self.__hostname = mapping_args.madmin_ip
        self.__port = mapping_args.madmin_port
        self.__retries = kwargs.get('retries', 1)
        self.__timeout = kwargs.get('timeout', 1)
        self.__protocol = 'http'  # madmin only runs on http unless behind a proxy so we can force http
        self.auth = (mapping_args.madmin_user, mapping_args.madmin_password)

    def prepare_request(self, request):
        """ Override the class function to create the URL with the URI and any other processing required """
        # Update the URL
        if request.url[0] == "/":
            request.url = request.url[1:]
        request.url = "%s://%s:%s/%s" % (self.__protocol, self.__hostname, self.__port, request.url)
        # We are logging this before calling super.prepare_request because the function will merge existing data
        # with the new request data.  This can cause a security risk where the authentication will be saved in
        # plain text on the filesystem in the log.
        if self.__logger:
            self.__logger.debug("Requests data: {}", str(request.__dict__))
        return super(LocalAPI, self).prepare_request(request)

    def send(self, request, **kwargs):
        """ Override the class function to handle retries and specific error codes """
        attempt = 0
        finished = False
        last_err = None
        # Apply the timeout to the send request
        if "timeout" not in kwargs or ("timeout" in kwargs and kwargs["timeout"] is None):
            kwargs["timeout"] = self.__timeout
        # Try the send until it finishes or we reach our maximum attempts
        while not finished and attempt < self.__retries:
            try:
                r = super(LocalAPI, self).send(request, **kwargs)
                if self.__logger:
                    self.__logger.debug("API Call completed in {}", str(r.elapsed))
                    self.__logger.debug("Status code: {}", str(r.status_code))
                # If we receive Bad Gateway the call is not completed and should be retried
                if r.status_code == 502:
                    if self.__logger:
                        self.__logger.debug("Bad Gateway received.")
                else:
                    return r
            except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as err:
                if self.__logger:
                    self.__logger.warning(err)
                last_err = err
            except Exception as err:
                if self.__logger:
                    self.__logger.warning("Unknown exception, {}", str(err))
                last_err = err
            # We did not finish successfully so sleep and increment the attempt
            attempt += 1
            # Only sleep if there are still retries left
            if attempt < self.__retries:
                time.sleep(self.__sleep_time)
        # We were unable to complete the call successfully so raise the last error
        raise last_err
