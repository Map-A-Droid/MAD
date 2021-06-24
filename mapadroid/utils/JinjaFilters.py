import base64
import json
from typing import Dict, Optional, Union

import jinja2
from yarl import URL

from mapadroid.utils.json_encoder import MADEncoder


def base64Filter(input: str) -> str:
    """Custom filter"""
    encoded = base64.b64encode(input.encode("utf-8"))
    return str(encoded, "utf-8")


def mad_json_filter(input: object) -> str:
    text = json.dumps(input, indent=None, cls=MADEncoder)
    return text


@jinja2.contextfunction
def subapp_url(context,
               subapp_name: str,
    __route_name: str,
    query_: Optional[Dict[str, str]] = None,
    **parts: Union[str, int]
) -> URL:
    app = context["app"][subapp_name]

    parts_clean: Dict[str, str] = {}
    for key in parts:
        val = parts[key]
        if isinstance(val, str):
            # if type is inherited from str expilict cast to str makes sense
            # if type is exactly str the operation is very fast
            val = str(val)
        elif type(val) is int:
            # int inherited classes like bool are forbidden
            val = str(val)
        else:
            raise TypeError(
                "argument value should be str or int, "
                "got {} -> [{}] {!r}".format(key, type(val), val)
            )
        parts_clean[key] = val

    url = app.router[__route_name].url_for(**parts_clean)
    if query_:
        url = url.with_query(query_)
    return url
