import copy

from mapadroid.tests import api_base
from mapadroid.tests import test_variables as global_variables


class APIRouteCalc(api_base.APITestBase):
    uri = copy.copy(global_variables.DEFAULT_OBJECTS['routecalc']['uri'])
    base_payload = copy.copy(global_variables.DEFAULT_OBJECTS['routecalc']['payload'])

    def test_landing_page(self):
        super().landing_page()
        self.remove_resources()

    def test_invalid_uri(self):
        super().invalid_uri()
        self.remove_resources()

    def test_invalid_post(self):
        payload = {
            'routefile': 'not a list',
        }
        errors = {'invalid': [
            ['routefile', 'Comma-delimited list'],
            ['routefile', 'Must be one coord set per line (float,float)']
        ]}
        super().invalid_post(payload, errors)
        self.remove_resources()

    def test_valid_post(self):
        super().valid_post(self.base_payload, self.base_payload)
        self.remove_resources()

    def test_invalid_put(self):
        payload = {
            'routefile': 'not a list',
        }
        errors = {'invalid': [
            ['routefile', 'Comma-delimited list'],
            ['routefile', 'Must be one coord set per line (float,float)']
        ]}
        super().invalid_put(payload, errors)
        self.remove_resources()

    def test_valid_put(self):
        super().valid_put(self.base_payload, self.base_payload)
        self.remove_resources()

    def test_invalid_patch(self):
        payload = {
            'namez': 'update',
        }
        errors = {"unknown": ["namez"]}
        super().invalid_patch(payload, errors)
        self.remove_resources()

    def test_valid_patch(self):
        payload = {
            'routefile': ['1,1'],
        }
        result = copy.copy(self.base_payload)
        result.update(payload)
        self.valid_patch(payload, result)
        self.remove_resources()
