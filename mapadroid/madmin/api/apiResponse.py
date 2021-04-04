import json

from aiohttp import web
from loguru import logger

from mapadroid.utils.json_encoder import MADEncoder

from . import apiException


class APIResponse(object):
    def __init__(self, request: web.Request, **kwargs):
        self.request = request
        self.headers = self.request.headers
        self.mimetype = self.request.content_type

    def __call__(self, content, status_code, **kwargs) -> web.Response:
        converted_data = self.convert_to_format(content)
        resp = web.Response(body=converted_data, content_type=self.mimetype)
        resp.status_code = status_code
        for key, value in kwargs.items():
            if key == 'headers':
                for header_key, header_val in value.items():
                    resp.headers.add(header_key, header_val)
            else:
                setattr(resp, key, value)
        logger.debug4('Return Data: {}', converted_data)
        logger.debug4('Return Headers: {}', resp.headers)
        return resp

    def convert_to_format(self, content):
        beautify = self.headers.get('X-Beautify')
        if self.mimetype == 'application/json':
            try:
                indent = None
                if beautify and beautify.isdigit() and int(beautify) == 1:
                    indent = 4
                return json.dumps(content, indent=indent, cls=MADEncoder)
            except Exception as err:
                raise apiException.FormattingError(500, err)
