import base64
import json

from mapadroid.utils.json_encoder import MADEncoder


def base64Filter(input: str) -> str:
    """Custom filter"""
    encoded = base64.b64encode(input.encode("utf-8"))
    return str(encoded, "utf-8")


def mad_json_filter(input: object) -> str:
    text = json.dumps(input, indent=None, cls=MADEncoder)
    return text
