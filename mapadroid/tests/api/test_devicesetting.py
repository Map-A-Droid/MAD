import copy

from mapadroid.tests import api_base
from mapadroid.tests import test_variables as global_variables


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
        self.remove_resources()

    def test_valid_post(self):
        super().valid_post(self.base_payload, self.base_payload)
        self.remove_resources()

    def test_invalid_put(self):
        payload = copy.copy(self.base_payload)
        del payload['devicepool']
        errors = {"missing": ["devicepool"]}
        super().invalid_put(payload, errors)
        self.remove_resources()

    def test_valid_put(self):
        super().valid_put(self.base_payload, self.base_payload)
        self.remove_resources()

    def test_invalid_patch(self):
        base_payload = {
            'devicepool': ''
        }
        errors = {"missing": ["devicepool"]}
        super().invalid_patch(base_payload, errors)
        self.remove_resources()

    def test_valid_patch(self):
        payload = {
            'settings': {
                'screenshot_type': 'png'
            }
        }
        result = copy.copy(self.base_payload)
        result['settings']['screenshot_type'] = 'png'
        self.valid_patch(payload, result)
        self.remove_resources()

    def test_pool_dependecy(self):
        device_obj = super().create_valid_resource('device')
        response = self.delete_resource(device_obj['resources']['pool']['uri'])
        self.assertEqual(response.status_code, 412)
        self.remove_resources()
