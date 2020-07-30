from unittest import TestCase
from mapadroid.tests.local_api import LocalAPI
from mapadroid.tests.test_utils import ResourceCreator


class APITestBase(TestCase, object):
    generated_uris = []
    index = 0

    def setUp(self):
        self.api = LocalAPI()
        self.creator = ResourceCreator(self.api)

    def tearDown(self):
        self.creator.remove_resources()
        self.api.close()

    def create_resource(self, uri, payload, **kwargs):
        response = self.creator.create_resource(uri, payload, **kwargs)
        self.assertEqual(response.status_code, 201)
        return response

    def delete_resource(self, uri):
        return self.creator.delete_resource(uri)

    def create_valid(self, payload, uri=None, **kwargs):
        uri = uri if uri else self.uri
        return self.create_resource(uri, payload, **kwargs)

    def remove_resources(self):
        self.creator.remove_resources()

    # ===========================
    # ===== Basic Resources =====
    # ===========================
    def create_valid_resource(self, resource, **kwargs):
        elem, response = self.creator.create_valid_resource(resource, **kwargs)
        self.assertEqual(response.status_code, 201)
        elem['uri'] = response.headers['X-Uri']
        return elem

    def get_valid_resource(self, resource, **kwargs):
        return self.creator.get_valid_resource(resource, **kwargs)

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
        for key, value in response.json().items():
            self.assertTrue(type(value) is dict)

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
