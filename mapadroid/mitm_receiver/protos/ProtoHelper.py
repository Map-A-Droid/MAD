import pickle
from typing import Any


class ProtoHelper:
    """
    Utility class to pickle/unpickle protos for handling with, e.g., Redis
    """

    @staticmethod
    def pickle(obj) -> bytes:
        return pickle.dumps(obj)

    @staticmethod
    def unpickle(val: bytes) -> Any:
        return pickle.loads(val)

    @staticmethod
    def decode(encoded_val: str) -> bytes:
        """
        PD encodes the raw protos in HEX for JSON serialization
        """
        return bytes.fromhex(encoded_val)
