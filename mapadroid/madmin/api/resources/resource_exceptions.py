from ..apiException import APIException


class InvalidIdentifier(APIException):
    def __init__(self):
        super(InvalidIdentifier, self).__init__(404)


class InvalidMode(APIException):
    def __init__(self):
        super(InvalidMode, self).__init__(400)


class NoModeSpecified(APIException):
    def __init__(self):
        super(NoModeSpecified, self).__init__(400)
