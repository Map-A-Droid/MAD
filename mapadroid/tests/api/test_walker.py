import copy

from mapadroid.tests import api_base
from mapadroid.tests import test_variables as global_variables


class APIWalker(api_base.APITestBase):
    uri = copy.copy(global_variables.DEFAULT_OBJECTS['walker']['uri'])
    base_payload = copy.copy(global_variables.DEFAULT_OBJECTS['walker']['payload'])

    def test_landing_page(self):
        super().landing_page()

    def test_invalid_uri(self):
        super().invalid_uri()

    def test_invalid_post(self):
        payload = copy.copy(self.base_payload)
        del payload['walkername']
        errors = {"missing": ["walkername"]}
        super().invalid_post(payload, errors)
        self.remove_resources()

    def test_valid_post(self):
        super().valid_post(self.base_payload, self.base_payload)

    def test_invalid_put(self):
        payload = copy.copy(self.base_payload)
        del payload['walkername']
        errors = {"missing": ["walkername"]}
        super().invalid_put(payload, errors)
        self.remove_resources()

    def test_valid_put(self):
        payload = copy.copy(self.base_payload)
        super().valid_put(payload, payload)
        self.remove_resources()

    def test_invalid_patch(self):
        payload = {
            'setup': 'String'
        }
        errors = {
            'invalid': [['setup', 'Comma-delimited list']],
            'invalid_uri': [['setup', 'walkerarea', 'String']]
        }
        super().invalid_patch(payload, errors)
        self.remove_resources()

    def test_valid_patch(self):
        super().valid_patch(self.base_payload, self.base_payload)

    def test_device_dependency(self):
        device_obj = super().create_valid_resource('device')
        response = self.api.delete(device_obj['resources']['walker']['uri'])
        self.assertEqual(response.status_code, 412)
        self.remove_resources()

    def test_walkerarea_dependency(self):
        device_obj = super().create_valid_resource('device')
        response = self.api.delete(device_obj['resources']['walker']['resources']['walkerarea']['uri'])
        self.assertEqual(response.status_code, 412)
        self.remove_resources()

    def test_walkerarea_cleanup(self):
        walker_obj = super().create_valid_resource('walker')
        self.delete_resource(walker_obj['uri'])
        response = self.api.get(walker_obj['resources']['walkerarea']['uri'])
        self.assertEqual(response.status_code, 404)
        self.remove_resources()

    def test_walkerarea_single_removal(self):
        walker_obj1 = super().create_valid_resource('walker')
        walker_obj2 = super().create_valid_resource('walker')
        payload = {
            'setup': [walker_obj1['resources']['walkerarea']['uri']]
        }
        self.api.patch(walker_obj2['uri'], json=payload)
        payload = {
            'setup': []
        }
        self.api.patch(walker_obj1['uri'], json=payload)
        response = self.api.get(walker_obj1['resources']['walkerarea']['uri'])
        self.assertEqual(response.status_code, 200)
        self.api.patch(walker_obj2['uri'], json=payload)
        response = self.api.get(walker_obj1['resources']['walkerarea']['uri'])
        self.assertEqual(response.status_code, 404)
        self.remove_resources()

    def test_walkerarea_response(self):
        walker_obj = super().create_valid_resource('walker')
        walker_data = self.api.get(walker_obj['uri'])
        self.assertTrue(walker_obj['resources']['walkerarea']['uri'] in walker_data.json()['setup'])
        self.remove_resources()

    def test_missing_required_variable_with_empty(self):
        payload = {
            'walkername': 'UnitTest Walker'
        }
        walker_uri = super().create_valid(payload).headers['X-Uri']
        walker_data = self.api.get(walker_uri)
        self.assertTrue('setup' in walker_data.json())
        self.remove_resources()

    def test_empty_setup(self):
        walker_obj = super().create_valid_resource('walker')
        payload = {
            'setup': None
        }
        response = self.api.patch(walker_obj['uri'], json=payload)
        self.assertEqual(response.status_code, 204)
        walker_data = self.api.get(walker_obj['uri'])
        self.assertTrue('setup' in walker_data.json())

    def test_walkerarea_append(self):
        walker_obj = super().create_valid_resource('walker')
        payload = {
            'setup': [walker_obj['resources']['walkerarea']['uri']]
        }
        headers = {
            'X-Append': '1'
        }
        self.api.patch(walker_obj['uri'], json=payload, headers=headers)
        response = self.api.get(walker_obj['uri'])
        expected_setup = [walker_obj['resources']['walkerarea']['uri'],
                          walker_obj['resources']['walkerarea']['uri']]
        self.assertEqual(response.json()['setup'], expected_setup)
