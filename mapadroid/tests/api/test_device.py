import copy
from mapadroid.tests import api_base
from mapadroid.tests import test_variables as global_variables


class APIDevice(api_base.APITestBase):
    uri = copy.copy(global_variables.DEFAULT_OBJECTS['device']['uri'])
    base_payload = copy.copy(global_variables.DEFAULT_OBJECTS['device']['payload'])

    def test_landing_page(self):
        super().landing_page()

    def test_invalid_uri(self):
        super().invalid_uri()

    def test_invalid_post(self):
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

    def test_ggl_as_ptc(self):
        pogoauth = super().create_valid_resource('pogoauth')
        payload = copy.copy(global_variables.DEFAULT_OBJECTS['device']['payload'])
        payload['ptc_login'] = [pogoauth['uri']]
        res = self.api.post(global_variables.DEFAULT_OBJECTS['device']['uri'], json=payload)
        self.assertTrue(res.status_code == 422)
        self.assertTrue('invalid' in res.json())
        self.assertTrue(res.json()['invalid'][0][0] == 'ptc_login')

    def test_ptc_as_ggl(self):
        payload = copy.copy(global_variables.DEFAULT_OBJECTS['pogoauth']['payload'])
        payload['login_type'] = 'ptc'
        pogoauth = super().create_valid_resource('pogoauth', payload=payload)
        payload = copy.copy(global_variables.DEFAULT_OBJECTS['device']['payload'])
        payload['ggl_login'] = pogoauth['uri']
        res = self.api.post(global_variables.DEFAULT_OBJECTS['device']['uri'], json=payload)
        self.assertTrue(res.status_code == 422)
        self.assertTrue('invalid' in res.json())
        self.assertTrue(res.json()['invalid'][0][0] == 'ggl_login')

    def test_duplicate_mac(self):
        payload = copy.copy(global_variables.DEFAULT_OBJECTS['device']['payload'])
        payload['mac_address'] = '00:1F:F3:00:1F:F3'
        super().create_valid_resource('device', payload=payload)
        res = self.api.post(global_variables.DEFAULT_OBJECTS['device']['uri'], json=payload)
        self.assertTrue(res.status_code == 422)
