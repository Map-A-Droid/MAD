import flask
import json
from . import apiException
from mapadroid.utils.json_encoder import MAD_Encoder


class APIResponse(object):
    def __init__(self, logger, request, **kwargs):
        self.logger = logger
        self.request = request
        self.headers = self.request.headers
        self.mimetype = self.request.accept

    def __call__(self, content, status_code, **kwargs):
        converted_data = self.convert_to_format(content)
        resp = flask.Response(converted_data, mimetype=self.mimetype)
        resp.status_code = status_code
        for key, value in kwargs.items():
            if key == 'headers':
                for header_key, header_val in value.items():
                    resp.headers.add(header_key, header_val)
            else:
                setattr(resp, key, value)
        self.logger.debug4('Return Data: {}', converted_data)
        self.logger.debug4('Return Headers: {}', resp.headers)
        return resp

    def convert_to_format(self, content):
        beautify = self.headers.get('X-Beautify')
        if self.mimetype == 'application/json':
            try:
                indent = None
                if beautify and beautify.isdigit() and int(beautify) == 1:
                    indent = 4
                return json.dumps(content, indent=indent, cls=MAD_Encoder)
            except Exception as err:
                raise apiException.FormattingError(500, err)
