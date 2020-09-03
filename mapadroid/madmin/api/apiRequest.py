import json

from . import apiException, global_variables


class APIRequest(object):
    """ Basic processing of the API Request to pull out required information

    Args:
        logger (loguru.logger): MADmin debug logger
        request (flask.request): Incoming request

    Attributes:
        accept (str): Requested content-type (accept-header) on the response
        content_type (str): Content-Type from the request
        data (mixed): Parsed data from the request
        headers (dict): Headers from the request
        _logger (loguru.logger): MADmin debug logger
        _request (flask.request): Incoming request
        params (dict): Parameters from the request
    """

    def __init__(self, logger, request):
        self._logger = logger
        self._request = request
        self.content_type = None
        self.accept = None
        self.data = None
        self.params = request.args
        self.headers = request.headers

    def __call__(self):
        self.process_request()
        self.parse_data()

    def parse_data(self):
        """ Transform the incoming data into a dataset python can utilize """
        data = self._request.get_data()
        self._logger.debug4('Incoming data: {}', data)
        if data is None or len(data) == 0:
            self.data = None
        elif self.content_type == 'application/json':
            try:
                self.data = json.loads(data)
            except ValueError:
                raise apiException.FormattingError('Invalid JSON.  Please validate the information')
        elif self.content_type == 'application/json-rpc':
            try:
                self.data = json.loads(data)
                self.data['call']
            except (ValueError, KeyError):
                raise apiException.FormattingError('Invalid RPC definition')
        elif self.content_type == 'application/octet-stream':
            self.data = data
        elif 'multipart/form-data' in self.content_type:
            self.data = {
                'files': self._request.files,
                'data': self._request.form
            }
        else:
            raise apiException.ContentException(415)

    def process_request(self):
        # Determine the content-type of the request and convert accordingly
        content_type = self._request.mimetype
        if not content_type:
            content_type = global_variables.DEFAULT_FORMAT.lower()
        else:
            content_type = content_type.lower()
        self.content_type = content_type
        self._logger.debug4('Requested content-type: {}', self.content_type)
        # Determine the requested response from the accept header.  Use the first valid one that is returned
        accept = self._request.headers.get('Accept')
        if not accept:
            accept = global_variables.DEFAULT_FORMAT.lower()
        else:
            accept = [x.lower() for x in accept.split(',')]
        valid_accept = False
        for accept_format in accept:
            if '*/*' in accept_format:
                accept = global_variables.DEFAULT_FORMAT.lower()
                valid_accept = True
                break
            if accept_format in global_variables.SUPPORTED_FORMATS:
                accept = accept_format
                valid_accept = True
                break
        if not valid_accept:
            raise apiException.AcceptException(415)
        self.accept = accept
        self._logger.debug4('Accept format: {}', accept)
