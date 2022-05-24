import base64
import json
from typing import Dict, Optional, Union

import jinja2
from yarl import URL

from mapadroid.madmin.AbstractMadminRootEndpoint import FORWARDED_PATH_KEY
from mapadroid.utils.aiohttp import add_prefix_to_url
from mapadroid.utils.json_encoder import MADEncoder
from mapadroid.utils.logging import LoggerEnums, get_logger

logger = get_logger(LoggerEnums.system)


def base64Filter(input: str) -> str:
    """Custom filter"""
    encoded = base64.b64encode(input.encode("utf-8"))
    return str(encoded, "utf-8")


def mad_json_filter(input: object) -> str:
    text = json.dumps(input, indent=None, cls=MADEncoder)
    return text


@jinja2.pass_context
def subapp_url(context,
               subapp_name: str,
               __route_name: str,
               query_: Optional[Dict[str, str]] = None,
               **parts: Union[str, int]
               ) -> URL:
    # allows chaining of subapps...
    subapps = subapp_name.split("/")
    app = context["app"]
    for subapp in subapps:
        app = app[subapp]

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
    return add_prefix_to_url(context.get(FORWARDED_PATH_KEY), url)


@jinja2.pass_context
def url_for_forwarded(context,
                      __route_name: str,
                      query_: Optional[Dict[str, str]] = None,
                      **parts: Union[str, int]
                      ) -> URL:
    # TODO: Reduce copypasta by setting subapp default to None?
    app = context["app"]

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
    router = app.router[__route_name]
    url = router.url_for(**parts_clean)
    if query_:
        url = url.with_query(query_)
    forwarded_path: Optional[str] = context.get(FORWARDED_PATH_KEY)
    final_url = add_prefix_to_url(forwarded_path, url)
    return final_url


@jinja2.pass_context
def subapp_static(context, subapp_name: Optional[str], static_file_path: str) -> str:
    return get_static_path(context, subapp_name, static_file_path)


@jinja2.pass_context
def static_forwarded(context, static_file_path: str) -> str:
    return get_static_path(context, None, static_file_path)


def get_static_path(context, subapp_name: Optional[str], static_file_path: str) -> str:
    """Filter for generating urls for static files.

    NOTE: you'll need
    to set app['static_root_url'] to be used as the root for the urls returned.

    Usage: {{ static('styles.css') }} might become
    "/static/styles.css" or "http://mycdn.example.com/styles.css"
    """
    app = context["app"]
    if subapp_name:
        # allows chaining of subapps...
        subapps = subapp_name.split("/")
        for subapp in subapps:
            app = app[subapp]

    try:
        static_url = app["static_root_url"]
    except KeyError:
        raise RuntimeError(
            "app does not define a static root url "
            "'static_root_url', you need to set the url root "
            "with app['static_root_url'] = '<static root>'."
        ) from None
    path = "/{}/{}".format(static_url.lstrip("/").rstrip("/"), static_file_path.lstrip("/"))
    if subapp_name:
        path = "/{}/{}".format(subapp_name.lstrip("/").rstrip("/"), path.lstrip("/"))
    forwarded_path: Optional[str] = context.get(FORWARDED_PATH_KEY)
    final_url = add_prefix_to_url(forwarded_path, URL(path))
    return str(final_url)
