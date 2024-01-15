import base64
import json
import pickle
from collections.abc import MutableSequence
from typing import Any, Optional, Union, List, Dict

from google.protobuf.json_format import MessageToJson, MessageToDict
from google.protobuf.message import Message

from mapadroid.utils.ProtoIdentifier import ProtoIdentifier
import mapadroid.mitm_receiver.protos.Rpc_pb2 as pogoprotos


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
        return base64.b64decode(encoded_val)

    @staticmethod
    def parse(method: ProtoIdentifier, value: Union[bytes, str]) -> Any:
        if isinstance(value, str):
            value = ProtoHelper.decode(value)
        else:
            # already in bytes format which we need
            pass
        message: Optional[Message] = None
        if method == ProtoIdentifier.GMO:
            message: pogoprotos.GetMapObjectsOutProto = pogoprotos.GetMapObjectsOutProto()
        elif method == ProtoIdentifier.ENCOUNTER:
            message: pogoprotos.EncounterOutProto = pogoprotos.EncounterOutProto()
        elif method == ProtoIdentifier.GET_ROUTES:
            message: pogoprotos.GetRoutesOutProto = pogoprotos.GetRoutesOutProto()
        elif method == ProtoIdentifier.GYM_INFO:
            message: pogoprotos.GymGetInfoOutProto = pogoprotos.GymGetInfoOutProto()
        elif method == ProtoIdentifier.FORT_SEARCH:
            message: pogoprotos.FortSearchOutProto = pogoprotos.FortSearchOutProto()
        elif method == ProtoIdentifier.DISK_ENCOUNTER:
            message: pogoprotos.DiskEncounterOutProto = pogoprotos.DiskEncounterOutProto()
        elif method == ProtoIdentifier.INVENTORY:
            message: pogoprotos.GetHoloholoInventoryOutProto = pogoprotos.GetHoloholoInventoryOutProto()
        else:
            raise ValueError(f"Method {method} could not be parsed.")

        message.ParseFromString(value)
        return message

    @staticmethod
    def to_json(value: Union[Message, List[Message], MutableSequence]) -> str:
        if isinstance(value, Message):
            return MessageToJson(value)
        elif isinstance(value, list) or isinstance(value, MutableSequence):
            listed: List[Dict] = []
            [listed.append(MessageToDict(message)) for message in value]
            return json.dumps(listed)
        else:
            raise ValueError("Cannot convert passed value")
