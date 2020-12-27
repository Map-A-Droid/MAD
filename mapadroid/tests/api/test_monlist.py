import copy

from mapadroid.tests import api_base
from mapadroid.tests import test_variables as global_variables


class APIMonIVList(api_base.APITestBase):
    uri = copy.copy(global_variables.DEFAULT_OBJECTS['monivlist']['uri'])
    base_payload = copy.copy(global_variables.DEFAULT_OBJECTS['monivlist']['payload'])

    def test_landing_page(self):
        super().landing_page()

    def test_invalid_uri(self):
        super().invalid_uri()

    def test_invalid_post(self):
        payload = {
            'mon_ids_iv': [],
        }
        errors = {"missing": ['monlist']}
        super().invalid_post(payload, errors)
        self.remove_resources()

    def test_valid_post(self):
        super().valid_post(self.base_payload, self.base_payload)
        self.remove_resources()

    def test_invalid_put(self):
        payload = {
            'mon_ids_iv': [],
        }
        errors = {"missing": ['monlist']}
        super().invalid_put(payload, errors)
        self.remove_resources()

    def test_valid_put(self):
        payload = {
            'monlist': 'Test MonIV List',
            'mon_ids_iv': [1, 2, 3]
        }
        super().valid_put(payload, payload)
        self.remove_resources()

    def test_invalid_patch(self):
        payload = {
            'usernamez': 'update'
        }
        errors = {"unknown": ["usernamez"]}
        super().invalid_patch(payload, errors)
        self.remove_resources()

    def test_valid_patch(self, **kwargs):
        payload = {
            'monlist': 'update',
        }
        result = copy.copy(self.base_payload)
        result.update(payload)
        self.valid_patch(payload, result)
        self.remove_resources()

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
            'mon_ids_iv': [1, 2]
        }
        headers = {
            'X-Append': '1'
        }
        self.valid_patch(payload, result, original=original, headers=headers)
        self.remove_resources()

    def test_area_dependency(self):
        monivlist_obj = super().create_valid_resource('monivlist')
        area_obj = super().create_valid_resource('area')
        update = {
            'settings': {
                'mon_ids_iv': monivlist_obj['uri']
            }
        }
        self.api.patch(area_obj['uri'], json=update)
        response = super().delete_resource(monivlist_obj['uri'])
        self.assertEqual(response.status_code, 412)
        self.remove_resources()
