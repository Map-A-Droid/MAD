import copy
from unittest import TestCase
import api_base
import global_variables

class APIDevicePool(api_base.APITestBase):
    uri = copy.copy(global_variables.DEFAULT_OBJECTS['devicesetting']['uri'])
    base_payload = copy.copy(global_variables.DEFAULT_OBJECTS['devicesetting']['payload'])

    def test_landing_page(self):
        super().landing_page()

    def test_invalid_uri(self):
        super().invalid_uri()

    def test_invalid_post(self):
        payload = copy.copy(self.base_payload)
        del payload['devicepool']
        errors = {"missing": ["devicepool"]}
        super().invalid_post(payload, errors)

    def test_valid_post(self):
        super().valid_post(self.base_payload, self.base_payload)

    def test_invalid_put(self):
        payload = copy.copy(self.base_payload)
        del payload['devicepool']
        errors = {"missing": ["devicepool"]}
        super().invalid_put(payload, errors)

    def test_valid_put(self):
        super().valid_put(self.base_payload, self.base_payload)

    def test_invalid_patch(self):
        base_payload = {
            'devicepool': ''
        }
        errors = {"missing": ["devicepool"]}
        super().invalid_patch(base_payload, errors)

    def test_valid_patch(self):
        payload = {
            'settings': {
                'screenshot_type': 'png'
            }
        }
        result = copy.copy(self.base_payload)
        result.update(payload)
        self.valid_patch(payload, result)

    def test_pool_dependecy(self):
        walker_uri = super().create_valid_resource('walker')
        pool_uri = super().create_valid_resource('devicesetting')
        device_uri = super().create_valid_resource('device', walker=walker_uri, pool=pool_uri)
        response = self.delete_resource(pool_uri)
        self.assertEqual(response.status_code, 412)
