class DataManagerException(Exception):
    pass

class DependencyError(DataManagerException):
    def __init__(self, dependencies):
        self.dependencies = dependencies
        super().__init__(dependencies)

class IdentifierNotSpecified(DataManagerException):
    pass

class InvalidDataFormat(DataManagerException):
    def __init__(self, key, data, expected):
        super().__init__()
        self.key = key
        self.data = data
        self.expected = expected
        self.received = type(data)

class InvalidMode(DataManagerException):
    def __init__(self, mode):
        self.mode = mode
        super().__init__(mode)

class RequiredFieldRemoved(DataManagerException):
    pass

class UnknownIdentifier(DataManagerException):
    pass
