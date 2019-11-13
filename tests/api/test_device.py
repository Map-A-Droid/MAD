import copy
from unittest import TestCase
import api_base
import global_variables

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
        walker_uri = super().create_valid_resource('walker')
        payload = copy.copy(self.base_payload)
        payload['walker'] = walker_uri
        super().valid_post(payload, payload)
        self.remove_resources()

    def test_invalid_put(self):
        walker_uri = super().create_valid_resource('walker')
        payload = copy.copy(self.base_payload)
        payload['walker'] = walker_uri
        device_uri = super().create_valid_resource('device', walker=walker_uri)
        del payload['origin']
        errors = {"missing": ["origin"]}
        response = self.api.put(device_uri, json=payload)
        self.assertEqual(response.status_code, 422)
        self.assertDictEqual(response.json(), errors)
        self.remove_resources()

    def test_valid_put(self):
        walker_uri = super().create_valid_resource('walker')
        payload = copy.copy(self.base_payload)
        payload['walker'] = walker_uri
        device_uri = super().create_valid_resource('device', walker=walker_uri)
        response = self.api.put(device_uri, json=payload)
        self.assertEqual(response.status_code, 204)
        self.remove_resources()

    def test_invalid_patch(self):
        walker_uri = super().create_valid_resource('walker')
        payload = copy.copy(self.base_payload)
        payload['origin'] = ''
        device_uri = super().create_valid_resource('device', walker=walker_uri)
        response = self.api.patch(device_uri, json=payload)
        self.assertEqual(response.status_code, 422)
        self.remove_resources()

    def test_valid_patch(self):
        walker_uri = super().create_valid_resource('walker')
        payload = {
            'origin': 'Updated UnitTest'
        }
        device_uri = super().create_valid_resource('device', walker=walker_uri)
        response = self.api.patch(device_uri, json=payload)
        self.assertEqual(response.status_code, 204)
        self.remove_resources()
