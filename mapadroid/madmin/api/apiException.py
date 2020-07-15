from . import global_variables


class APIException(Exception):
    def __init__(self, status_code, reason=None):
        self.status_code = status_code
        self.reason = reason
        super(APIException, self).__init__(status_code, reason)


class AcceptException(APIException):
    def __repr__(self):
        return 'Invalid accept sent.  Allowed formats: %s' % (','.join(global_variables.SUPPORTED_FORMATS, ))


class ContentException(APIException):
    def __repr__(self):
        return 'Invalid content-type  Allowed formats: %s' % (','.join(global_variables.SUPPORTED_FORMATS, ))


class FormattingError(APIException):
    def __init__(self, invalid_data):
        super(FormattingError, self).__init__(422, reason=invalid_data)
