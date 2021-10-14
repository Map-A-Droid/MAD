from enum import Enum


class MitmMapperType(Enum):
    default = 'default'
    grpc = 'grpc'
    redis = 'redis'

    def __str__(self):
        return self.value
