import json
from datetime import datetime
from decimal import Decimal
from enum import Enum

from mapadroid.db.model import Base
from mapadroid.utils.collections import Location


class WebhookJsonEncoder(json.JSONEncoder):
    def encode(self, object_to_encode, *args, **kw):
        return super(WebhookJsonEncoder, self).encode(object_to_encode, *args, **kw)

    def default(self, obj):
        if isinstance(obj, type):
            return str(obj)
        elif isinstance(obj, datetime):
            return int(obj.timestamp())
        elif isinstance(obj, Decimal):
            return float(obj)
        elif isinstance(obj, Enum):
            return obj.value
        elif isinstance(obj, Location):
            return [obj.lat, obj.lng]
        elif isinstance(obj, Base):
            # Dumb serialization of a model class to json... excluding private/protected attributes
            # TODO: Recursion for the values accordingly...
            return {var: self.default(val) for var, val in vars(obj).items() if not var.startswith("_")}
        return json.JSONEncoder.default(self, obj)
