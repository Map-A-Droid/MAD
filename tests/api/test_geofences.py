import copy
from unittest import TestCase
import api_base
import global_variables

class APIGeoFence(api_base.APITestBase):
    uri = copy.copy(global_variables.DEFAULT_OBJECTS['geofence']['uri'])
    base_payload = copy.copy(global_variables.DEFAULT_OBJECTS['geofence']['payload'])

    def test_landing_page(self):
        super().landing_page()
        self.remove_resources()

    def test_invalid_uri(self):
        super().invalid_uri()
        self.remove_resources()

    def test_invalid_post(self):
        payload = {
            'name': '',
        }
        errors = {"missing": ["name", 'fence_type']}
        super().invalid_post(payload, errors)
        self.remove_resources()

    def test_valid_post(self):
        super().valid_post(self.base_payload, self.base_payload)
        self.remove_resources()

    def test_invalid_put(self):
        payload = {
            'name': '',
        }
        errors = {"missing": ["name", 'fence_type']}
        super().invalid_put(payload, errors)
        self.remove_resources()

    def test_valid_put(self):
        payload = {
            'name': 'update',
            'fence_type': 'polygon'
        }
        result = copy.copy(payload)
        result['fence_data'] = []
        super().valid_put(payload, result)
        self.remove_resources()

    def test_invalid_patch(self):
        payload = {
            'namez': 'update',
        }
        errors = {"unknown": ["namez"]}
        super().invalid_patch(payload, errors)
        self.remove_resources()

    def test_valid_patch(self):
        payload = {
            'name': 'Updated GeoFence',
        }
        result = copy.copy(self.base_payload)
        result.update(payload)
        self.valid_patch(payload, result)
        self.remove_resources()
