import copy
import local_api
from collections import namedtuple
from unittest import TestCase
import global_variables

class APITestBase(TestCase):
    generated_uris = []

    def setUp(self):
        madmin_args = namedtuple('madmin_args', 'madmin_ip madmin_port madmin_user madmin_password')
        args = madmin_args('127.0.0.1', '5000', '', '')
        self.api = local_api.LocalAPI(None, args)

    def tearDown(self):
        self.remove_resources()
        self.api.close()

    def remove_resources(self):
        if self.generated_uris:
            for uri in set(reversed(self.generated_uris)):
                self.delete_resource(uri)

    def add_created_resource(self, uri):
        if uri not in self.generated_uris:
            self.generated_uris.append(uri)

    def create_resource(self, uri, payload, **kwargs):
        response = self.api.post(uri, json=payload, **kwargs)
        self.assertEqual(response.status_code, 201)
        created_uri = response.headers['X-Uri']
        self.add_created_resource(created_uri)
        return response

    def delete_resource(self, uri):
        response = self.api.delete(uri)
        if response.status_code in [202, 404] and uri in self.generated_uris:
            self.generated_uris.remove(uri)
        return response

    def create_valid(self, payload, uri=None, **kwargs):
        uri = uri if uri else self.uri
        return self.create_resource(uri, payload, **kwargs)

    # ===========================
    # ===== Basic Resources =====
    # ===========================
    def create_valid_resource(self, resource, **kwargs):
        resource_def = global_variables.DEFAULT_OBJECTS[resource]
        payload = copy.copy(resource_def['payload'])
        def_kwargs = resource_def.get('kwargs', {})
        if kwargs:
            for key, val in kwargs.items():
                payload[key] = val
        response = self.create_resource(resource_def['uri'], payload, **def_kwargs)
        self.assertEqual(response.status_code, 201)
        return response.headers['X-Uri']

    # ===========================
    # ========== Tests ==========
    # ===========================
    def landing_page(self, test_resource=True):
        response = self.api.get(self.uri)
        self.assertEqual(response.status_code, 200)
        json_data = response.json()
        self.assertTrue('resource' in json_data)
        self.assertTrue('results' in json_data)
        if test_resource:
            self.assertTrue(len(json_data['resource']['fields']) > 0)
            if 'settings' in json_data['resource']:
                self.assertTrue(len(json_data['resource']['settings']) > 0)
        params = {
            'hide_resource': 1
        }
        response = self.api.get(self.uri, params=params)
        self.assertEqual(response.status_code, 200)
        self.assertFalse('resource' in response.json())
        self.assertTrue(type(response.json()) is dict)
        params['fetch_all'] = 1
        response = self.api.get(self.uri, params=params)
        self.assertEqual(response.status_code, 200)
        for key, val in response.json().items():
            self.assertTrue(type(val) is dict)

    def invalid_uri(self):
        path = '%s/%s' % (self.uri, '-1')
        response = self.api.get(path)
        self.assertEqual(response.status_code, 404)

    def invalid_post(self, payload, errors, error_code=422, **kwargs):
        response = self.api.post(self.uri, json=payload, **kwargs)
        self.assertEqual(response.status_code, error_code)
        self.assertDictEqual(response.json(), errors)

    def valid_post(self, payload, result, **kwargs):
        response = self.create_valid(payload, **kwargs)
        self.assertEqual(response.status_code, 201)
        self.assertDictEqual(result, response.json())
        uri = response.headers['X-Uri']
        response = self.delete_resource(uri)
        self.assertEqual(response.status_code, 202)

    def invalid_put(self, payload, errors, error_code=422, **kwargs):
        response = self.create_valid(self.base_payload)
        uri = response.headers['X-Uri']
        response = self.api.put(uri, json=payload, **kwargs)
        self.assertEqual(response.status_code, error_code)
        self.assertDictEqual(response.json(), errors)
        response = self.delete_resource(uri)
        self.assertEqual(response.status_code, 202)

    def valid_put(self, payload, result, **kwargs):
        response = self.create_valid(self.base_payload)
        uri = response.headers['X-Uri']
        response = self.api.put(uri, json=payload, **kwargs)
        self.assertEqual(response.status_code, 204)
        response = self.api.get(uri)
        self.assertDictEqual(result, response.json())
        response = self.delete_resource(uri)

    def invalid_patch(self, payload, errors, error_code=422, **kwargs):
        response = self.create_valid(self.base_payload)
        uri = response.headers['X-Uri']
        response = self.api.patch(uri, json=payload, **kwargs)
        self.assertEqual(response.status_code, error_code)
        self.assertDictEqual(errors, response.json())
        response = self.delete_resource(uri)

    def valid_patch(self, payload, result, original=None, **kwargs):
        base_payload = original if original else self.base_payload
        response = self.create_valid(base_payload)
        uri = response.headers['X-Uri']
        response = self.api.patch(uri, json=payload, **kwargs)
        self.assertEqual(response.status_code, 204)
        response = self.api.get(uri)
        self.assertDictEqual(result, response.json())
        response = self.delete_resource(uri)
