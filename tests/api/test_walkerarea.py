import copy
from unittest import TestCase
import api_base
import global_variables

class APIWalkerArea(api_base.APITestBase):
    uri = copy.copy(global_variables.DEFAULT_OBJECTS['walkerarea']['uri'])
    base_payload = copy.copy(global_variables.DEFAULT_OBJECTS['walkerarea']['payload'])

    def test_landing_page(self):
        super().landing_page()

    def test_invalid_uri(self):
        super().invalid_uri()

    def test_invalid_post(self):
        payload = copy.copy(self.base_payload)
        del payload['walkerarea']
        errors = {"missing": ["walkerarea"]}
        super().invalid_post(payload, errors)
        self.remove_resources()

    def test_invalid_area(self):
        payload = copy.copy(self.base_payload)
        errors = {
            'invalid': [['walkerarea', 'Integer (1,2,3)']],
            'invalid_uri': [['walkerarea', 'area', 'UnitTest WalkerArea']]
        }
        super().invalid_post(payload, errors)
        self.remove_resources()

    def test_valid_post(self):
        area_uri = super().create_valid_resource('area')
        payload = copy.copy(self.base_payload)
        payload['walkerarea'] = area_uri
        super().valid_post(payload, payload)
        self.remove_resources()

    def test_valid_post_missing_fields(self):
        area_uri = super().create_valid_resource('area')
        payload = copy.deepcopy(self.base_payload)
        result = copy.deepcopy(payload)
        result['walkerarea'] = area_uri
        payload['walkerarea'] = area_uri
        del payload['walkervalue']
        super().valid_post(payload, result)
        self.remove_resources()

    def test_invalid_put(self):
        area_uri = super().create_valid_resource('area')
        walkerarea_uri = super().create_valid_resource('walkerarea', walkerarea=area_uri)
        payload = copy.copy(self.base_payload)
        del payload['walkerarea']
        errors = {"missing": ["walkerarea"]}
        response = self.api.put(walkerarea_uri, json=payload)
        self.assertEqual(response.status_code, 422)
        self.assertDictEqual(response.json(), errors)
        self.remove_resources()

    def test_valid_put(self):
        area_uri = super().create_valid_resource('area')
        walkerarea_uri = super().create_valid_resource('walkerarea', walkerarea=area_uri)
        payload = copy.copy(self.base_payload)
        payload['walkerarea'] = area_uri
        response = self.api.put(walkerarea_uri, json=payload)
        self.assertEqual(response.status_code, 204)
        self.remove_resources()

    def test_invalid_patch(self):
        area_uri = super().create_valid_resource('area')
        walkerarea_uri = super().create_valid_resource('walkerarea', walkerarea=area_uri)
        payload = {
            'walkerarea': ''
        }
        errors = {
            "missing": ["walkerarea"],
            'invalid': [['walkerarea', 'Integer (1,2,3)']],
            'invalid_uri': [['walkerarea', 'area', '']]
        }
        response = self.api.patch(walkerarea_uri, json=payload)
        self.assertEqual(response.status_code, 422)
        self.assertDictEqual(response.json(), errors)
        self.remove_resources()

    def test_valid_patch(self):
        area_uri = super().create_valid_resource('area')
        walkerarea_uri = super().create_valid_resource('walkerarea', walkerarea=area_uri)
        payload = {
            'walkertext': 'Updated UnitTest'
        }
        response = self.api.patch(walkerarea_uri, json=payload)
        self.assertEqual(response.status_code, 204)
        self.remove_resources()

    def test_walker_dependency(self):
        area_uri = super().create_valid_resource('area')
        walkerarea_uri = super().create_valid_resource('walkerarea', walkerarea=area_uri)
        walker_uri = super().create_valid_resource('walker', setup=[walkerarea_uri])
        response = self.api.delete(walkerarea_uri)
        self.assertEqual(response.status_code, 412)
        self.remove_resources()

    def test_walkerarea_cleanup(self):
        area_uri = super().create_valid_resource('area')
        walkerarea_uri = super().create_valid_resource('walkerarea', walkerarea=area_uri)
        walker_uri = super().create_valid_resource('walker', setup=[walkerarea_uri])
        self.delete_resource(walker_uri)
        response = self.api.get(walkerarea_uri)
        self.assertEqual(response.status_code, 404)
        self.remove_resources()
