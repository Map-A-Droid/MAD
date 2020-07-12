DEFAULT_FORMAT = 'application/json'
DEFAULT_HEADERS = {
    'application/json': {
        'content-type': 'application/json'
    }
}
# These conversions need to be defined in .apiHandler.apiRequest.parse_data and
# .apiResponse.APIResponse.convert_to_format
SUPPORTED_FORMATS = [
    'application/json',
    'application/json-rpc',
    'application/octet-stream'
]
