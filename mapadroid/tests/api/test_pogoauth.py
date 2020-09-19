import copy
from mapadroid.tests import api_base
from mapadroid.tests import test_variables as global_variables


class APIPogoAuth(api_base.APITestBase):
    uri = copy.copy(global_variables.DEFAULT_OBJECTS['pogoauth']['uri'])
    base_payload = copy.copy(global_variables.DEFAULT_OBJECTS['pogoauth']['payload'])

    def test_landing_page(self):
        super().landing_page()
        self.remove_resources()

    def test_invalid_uri(self):
        super().invalid_uri()
        self.remove_resources()

    def test_invalid_post(self):
        payload = {
            'username': '',
        }
        errors = {"missing": ['login_type', "username", 'password']}
        super().invalid_post(payload, errors)
        self.remove_resources()

    def test_valid_post(self):
        super().valid_post(self.base_payload, self.base_payload)
        self.remove_resources()

    def test_invalid_put(self):
        payload = {
            'username': '',
            'password': 'pass',
            'login_type': 'google'
        }
        errors = {"missing": ["username"]}
        super().invalid_put(payload, errors)
        self.remove_resources()

    def test_valid_put(self):
        payload = {
            'username': 'update',
            'password': 'pass',
            'login_type': 'google'
        }
        super().valid_put(payload, payload)
        self.remove_resources()

    def test_invalid_patch(self):
        payload = {
            'usernamez': 'update',
            'password': 'pass',
            'login_type': 'google'
        }
        errors = {"unknown": ["usernamez"]}
        super().invalid_patch(payload, errors)
        self.remove_resources()

    def test_valid_patch(self):
        payload = {
            'username': 'update',
        }
        result = copy.copy(self.base_payload)
        result.update(payload)
        self.valid_patch(payload, result)
        self.remove_resources()

    def test_device_dependency(self):
        dev_info = super().create_valid_resource('device')
        pogo_payload = copy.copy(global_variables.DEFAULT_OBJECTS['pogoauth']['payload'])
        pogo_payload['device_id'] = dev_info['uri']
        pogoauth_obj = super().create_valid_resource('pogoauth', payload=pogo_payload)
        response = self.api.delete(pogoauth_obj['uri'])
        self.assertEqual(response.status_code, 412)
        self.remove_resources()

    def test_case_sensitivity_google(self):
        payload = copy.copy(APIPogoAuth.base_payload)
        payload["username"] = "POGOAUTH@gmail.com"
        elem, response = self.creator.create_valid_resource("pogoauth", payload=payload)
        self.assertTrue(response.json()["username"] == payload["username"].lower())

    def test_case_sensitivity_ptc(self):
        payload = copy.copy(APIPogoAuth.base_payload)
        payload["username"] = "POGOAUTH"
        payload["login_type"] = "ptc"
        elem, response = self.creator.create_valid_resource("pogoauth", payload=payload)
        self.assertTrue(response.json()["username"] == payload["username"])
