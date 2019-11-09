import copy
from unittest import TestCase
import api_base
import global_variables

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

    def test_valid_post(self):
        super().valid_post(self.base_payload, self.base_payload)

    def test_invalid_put(self):
        payload = copy.copy(self.base_payload)
        del payload['walkername']
        errors = {"missing": ["walkername"]}
        super().invalid_put(payload, errors)

    def test_valid_put(self):
        payload = copy.copy(self.base_payload)
        super().valid_put(payload, payload)

    def test_invalid_patch(self):
        payload = {
            'setup': 'String'
        }
        errors = {'Invalid URIs': ['String']}
        super().invalid_patch(payload, errors)

    def test_valid_patch(self):
        super().valid_patch(self.base_payload, self.base_payload)

    def test_device_dependency(self):
        walker_uri = super().create_valid_resource('walker')
        device_uri = super().create_valid_resource('device', walker=walker_uri)
        response = self.api.delete(walker_uri)
        self.assertEqual(response.status_code, 412)

    def test_walker_dependency(self):
        area_uri = super().create_valid_resource('area')
        walkerarea_uri = super().create_valid_resource('walkerarea', walkerarea=area_uri)
        walker_uri = super().create_valid_resource('walker', setup=[walkerarea_uri])
        response = self.api.delete(walkerarea_uri)
        self.assertEqual(response.status_code, 412)

    def test_walkerarea_cleanup(self):
        area_uri = super().create_valid_resource('area')
        walkerarea_uri = super().create_valid_resource('walkerarea', walkerarea=area_uri)
        walker_uri = super().create_valid_resource('walker', setup=[walkerarea_uri])
        self.delete_resource(walker_uri)
        response = self.api.get(walkerarea_uri)
        self.assertEqual(response.status_code, 404)

    def test_walkerarea_single_removal(self):
        area_uri = super().create_valid_resource('area')
        walkerarea_uri = super().create_valid_resource('walkerarea', walkerarea=area_uri)
        walker_uri = super().create_valid_resource('walker', setup=[walkerarea_uri])
        walker_uri2 = super().create_valid_resource('walker', setup=[walkerarea_uri])
        payload = {
            'setup': []
        }
        self.api.patch(walker_uri, json=payload)
        response = self.api.get(walkerarea_uri)
        self.assertEqual(response.status_code, 200)
        self.api.patch(walker_uri2, json=payload)
        response = self.api.get(walkerarea_uri)
        self.assertEqual(response.status_code, 404)

    def test_walkerarea_response(self):
        area_uri = super().create_valid_resource('area')
        walkerarea_uri = super().create_valid_resource('walkerarea', walkerarea=area_uri)
        walker_uri = super().create_valid_resource('walker', setup=[walkerarea_uri])
        walker_data = self.api.get(walker_uri)
        self.assertTrue(walkerarea_uri in walker_data.json()['setup'])

    def test_missing_required_variable_with_empty(self):
        payload = {
            'walkername': 'UnitTest Walker'
        }
        walker_uri = super().create_valid(payload).headers['X-Uri']
        walker_data = self.api.get(walker_uri)
        self.assertTrue('setup' in walker_data.json())

    def test_empty_setup(self):
        walker_uri = super().create_valid_resource('walker')
        payload = {
            'setup': None
        }
        response = self.api.patch(walker_uri, json=payload)
        self.assertEqual(response.status_code, 204)
