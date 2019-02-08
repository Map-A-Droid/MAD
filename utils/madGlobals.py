

class WebsocketWorkerRemovedException(Exception):
    pass


class WebsocketWorkerTimeoutException(Exception):
    pass


class InternalStopWorkerException(Exception):
    """
    Exception to be called in derived worker methods to signal stops of the worker
    """
    pass
