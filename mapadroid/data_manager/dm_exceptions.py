class DataManagerException(Exception):
    pass


class DependencyError(DataManagerException):
    def __init__(self, dependencies):
        self.dependencies = dependencies
        super().__init__(dependencies)


class InvalidArea(DataManagerException):
    pass


class InvalidSection(DataManagerException):
    pass


class ModeNotSpecified(DataManagerException):
    def __init__(self, mode):
        self.mode = mode
        super().__init__(mode)


class ModeUnknown(DataManagerException):
    def __init__(self, mode):
        self.mode = mode
        super().__init__(mode)


class SaveIssue(DataManagerException):
    def __init__(self, issue):
        self.issue = issue
        super().__init__(issue)


class UnknownIdentifier(DataManagerException):
    def __init__(self, identifiers=None):
        super().__init__()
        if identifiers:
            self.invalid = identifiers


class UpdateIssue(DataManagerException):
    def __init__(self, **kwargs):
        super().__init__()
        self.issues = {}
        for key, issue in kwargs.items():
            if not issue:
                continue
            self.issues[key] = issue
