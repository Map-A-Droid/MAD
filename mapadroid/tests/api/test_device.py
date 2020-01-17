import copy

from . import api_base
from . import global_variables


class APIDevice(api_base.APITestBase):
    uri = copy.copy(global_variables.DEFAULT_OBJECTS['device']['uri'])
    base_payload = copy.copy(global_variables.DEFAULT_OBJECTS['device']['payload'])

    def test_landing_page(self):
        super().landing_page()

    def test_invalid_uri(self):
        super().invalid_uri()

    def test_invalid_post(self):
        payload = copy.copy(self.base_payload)
        errors = {
            "missing": ["walker"]
        }
        super().invalid_post(self.base_payload, errors)
        self.remove_resources()

    def test_valid_post(self):
        super().create_valid_resource('device')
        self.remove_resources()

    def test_invalid_put(self):
        device_obj = super().create_valid_resource('device')
        dev_data = self.api.get(device_obj['uri']).json()
        del dev_data['origin']
        errors = {"missing": ["origin"]}
        response = self.api.put(device_obj['uri'], json=dev_data)
        self.assertEqual(response.status_code, 422)
        self.assertDictEqual(response.json(), errors)
        self.remove_resources()

    def test_valid_put(self):
        device_obj = super().create_valid_resource('device')
        dev_data = self.api.get(device_obj['uri']).json()
        response = self.api.put(device_obj['uri'], json=dev_data)
        self.assertEqual(response.status_code, 204)
        self.remove_resources()

    def test_invalid_patch(self):
        device_obj = super().create_valid_resource('device')
        payload = {'origin': ''}
        response = self.api.patch(device_obj['uri'], json=payload)
        self.assertEqual(response.status_code, 422)
        self.remove_resources()

    def test_valid_patch(self):
        device_obj = super().create_valid_resource('device')
        payload = {'origin': 'updated'}
        response = self.api.patch(device_obj['uri'], json=payload)
        self.assertEqual(response.status_code, 204)
        self.remove_resources()

    def test_clear_level(self):
        payload = {
            "call": "flush_level"
        }
        headers = {
            'Content-Type': 'application/json-rpc'
        }
        device_obj = super().create_valid_resource('device')
        response = self.api.post(device_obj['uri'], json=payload, headers=headers)
        self.assertEqual(response.status_code, 204)
        self.remove_resources()
