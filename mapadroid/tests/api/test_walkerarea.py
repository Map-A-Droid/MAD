import copy

from mapadroid.tests import api_base
from mapadroid.tests import test_variables as global_variables


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
        super().create_valid_resource('walkerarea')
        self.remove_resources()

    def test_valid_post_missing_fields(self):
        area_obj = super().create_valid_resource('area')
        payload = copy.deepcopy(self.base_payload)
        result = copy.deepcopy(payload)
        result['walkerarea'] = area_obj['uri']
        payload['walkerarea'] = area_obj['uri']
        result['eventid'] = ''
        del payload['walkervalue']
        super().valid_post(payload, result)
        self.remove_resources()

    def test_invalid_put(self):
        walkerarea_obj = super().create_valid_resource('walkerarea')
        payload = copy.copy(self.base_payload)
        del payload['walkerarea']
        errors = {"missing": ["walkerarea"]}
        response = self.api.put(walkerarea_obj['uri'], json=payload)
        self.assertEqual(response.status_code, 422)
        self.assertDictEqual(response.json(), errors)
        self.remove_resources()

    def test_valid_put(self):
        walkerarea_obj = super().create_valid_resource('walkerarea')
        payload = copy.copy(self.base_payload)
        payload['walkerarea'] = walkerarea_obj['resources']['area']['uri']
        response = self.api.put(walkerarea_obj['uri'], json=payload)
        self.assertEqual(response.status_code, 204)
        self.remove_resources()

    def test_invalid_patch(self):
        walkerarea_obj = super().create_valid_resource('walkerarea')
        payload = {
            'walkerarea': ''
        }
        errors = {
            "missing": ["walkerarea"],
            'invalid': [['walkerarea', 'Integer (1,2,3)']],
            'invalid_uri': [['walkerarea', 'area', '']]
        }
        response = self.api.patch(walkerarea_obj['uri'], json=payload)
        self.assertEqual(response.status_code, 422)
        self.assertDictEqual(response.json(), errors)
        self.remove_resources()

    def test_valid_patch(self):
        walkerarea_obj = super().create_valid_resource('walkerarea')
        payload = {
            'walkertext': 'Updated UnitTest'
        }
        response = self.api.patch(walkerarea_obj['uri'], json=payload)
        self.assertEqual(response.status_code, 204)
        self.remove_resources()

    def test_walker_dependency(self):
        walker_obj = super().create_valid_resource('walker')
        response = self.api.delete(walker_obj['resources']['walkerarea']['uri'])
        self.assertEqual(response.status_code, 412)
        self.remove_resources()

    def test_walkerarea_cleanup(self):
        walker_obj = super().create_valid_resource('walker')
        self.delete_resource(walker_obj['uri'])
        response = self.api.get(walker_obj['resources']['walkerarea']['uri'])
        self.assertEqual(response.status_code, 404)
        self.remove_resources()
