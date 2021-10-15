from enum import Enum


class MitmMapperType(Enum):
    standalone = 'standalone'
    grpc = 'grpc'
    redis = 'redis'

    def __str__(self):
        return self.value
