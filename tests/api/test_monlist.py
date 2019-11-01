import copy
from unittest import TestCase
import api_base
import global_variables

class APIMonIVList(api_base.APITestBase):
    uri = copy.copy(global_variables.DEFAULT_OBJECTS['monivlist']['uri'])
    base_payload = copy.copy(global_variables.DEFAULT_OBJECTS['monivlist']['payload'])

    def test_landing_page(self):
        super().landing_page()

    def test_invalid_uri(self):
        super().invalid_uri()

    def test_invalid_post(self):
        payload = {
            'monlist': 'Test',
        }
        errors = {"missing": ['mon_ids_iv']}
        super().invalid_post(payload, errors)

    def test_valid_post(self):
        super().valid_post(self.base_payload, self.base_payload)

    def test_invalid_put(self):
        payload = {
            'monlist': 'Test',
        }
        errors = {"missing": ["mon_ids_iv"]}
        super().invalid_put(payload, errors)

    def test_valid_put(self):
        payload = {
            'monlist': 'Test MonIV List',
            'mon_ids_iv': [1,2,3]
        }
        super().valid_put(payload, payload)

    def test_invalid_patch(self):
        payload = {
            'usernamez': 'update'
        }
        errors = {"unknown": ["usernamez"]}
        super().invalid_patch(payload, errors)

    def test_valid_patch(self, **kwargs):
        payload = {
            'monlist': 'update',
        }
        result = copy.copy(self.base_payload)
        result.update(payload)
        resp = self.create_valid(self.base_payload)
        self.valid_patch(payload, result)

    def test_append(self, **kwargs):
        original = {
            'monlist': 'Test MonIV List',
            'mon_ids_iv': [1]
        }
        payload = {
            'mon_ids_iv': [2]
        }
        result = {
            'monlist': 'Test MonIV List',
            'mon_ids_iv': [1,2]
        }
        headers = {
            'X-Append': '1'
        }
        self.valid_patch(payload, result, original=original, headers=headers)

    def test_area_dependency(self):
        monivlist_uri = super().create_valid_resource('monivlist')
        payload = {
            "coords_spawns_known": True,
            "geofence_included": "unit_test.txt",
            "init": False,
            "name": "Unit Test Area",
            "routecalc": "unit_test",
            "settings": {
                "starve_route": False,
                'mon_ids_iv': monivlist_uri
            }
        }
        headers = {
            'X-Mode': 'mon_mitm'
        }
        self.create_resource('/api/area', payload, headers=headers)
        response = super().delete_resource(monivlist_uri)
        self.assertEqual(response.status_code, 412)