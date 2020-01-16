import copy
from unittest import TestCase

from mapadroid.utils import local_api
from . import global_variables


class APITestBase(TestCase):
    generated_uris = []
    index = 0

    def setUp(self):
        self.api = local_api.LocalAPI()

    def tearDown(self):
        self.remove_resources()
        self.api.close()

    def remove_resources(self):
        if self.generated_uris:
            for uri in reversed(self.generated_uris):
                res = self.delete_resource(uri)

    def add_created_resource(self, uri):
        if uri not in self.generated_uris:
            self.generated_uris.append(uri)

    def create_resource(self, uri, payload, **kwargs):
        response = self.api.post(uri, json=payload, **kwargs)
        self.assertEqual(response.status_code, 201)
        created_uri = response.headers['X-Uri']
        self.add_created_resource(created_uri)
        self.index += 1
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
        uri, payload, headers, elem = self.get_valid_resource(resource, **kwargs)
        response = self.create_resource(uri, payload, headers=headers)
        self.assertEqual(response.status_code, 201)
        elem['uri'] = response.headers['X-Uri']
        return elem

    def get_valid_resource(self, resource, **kwargs):
        resource_def = global_variables.DEFAULT_OBJECTS[resource]
        try:
            payload = kwargs['payload']
            del kwargs['payload']
        except:
            payload = kwargs.get('payload', copy.copy(resource_def['payload']))
        headers = kwargs.get('headers', {})
        elem = {
            'uri': None,
            'resources': {}
        }
        name_elem = None
        if resource == 'area':
            elem['resources']['geofence_included'] = self.create_valid_resource('geofence')
            elem['resources']['routecalc'] = self.create_valid_resource('routecalc')
            payload['geofence_included'] = elem['resources']['geofence_included']['uri']
            payload['routecalc'] = elem['resources']['routecalc']['uri']
            payload['name'] %= self.index
            try:
                headers['X-Mode']
            except:
                headers['X-Mode'] = 'raids_mitm'
        elif resource == 'auth':
            name_elem = 'username'
        elif resource == 'device':
            elem['resources']['walker'] = self.create_valid_resource('walker')
            elem['resources']['pool'] = self.create_valid_resource('devicesetting')
            payload['walker'] = elem['resources']['walker']['uri']
            payload['pool'] = elem['resources']['pool']['uri']
            payload['origin'] %= self.index
        elif resource == 'devicesetting':
            name_elem = 'devicepool'
        elif resource == 'geofence':
            name_elem = 'name'
        elif resource == 'monivlist':
            name_elem = 'monlist'
        elif resource == 'walker':
            elem['resources']['walkerarea'] = self.create_valid_resource('walkerarea')
            payload['setup'] = [elem['resources']['walkerarea']['uri']]
            name_elem = 'walkername'
        elif resource == 'walkerarea':
            elem['resources']['area'] = self.create_valid_resource('area')
            payload['walkerarea'] = elem['resources']['area']['uri']
        payload = self.recursive_update(payload, kwargs)
        if name_elem and '%s' in payload[name_elem]:
            payload[name_elem] %= self.index
        return (resource_def['uri'], payload, headers, elem)

    def recursive_update(self, payload, elems):
        for key, val in elems.items():
            if key == 'headers':
                continue
            elif type(val) == dict:
                payload[key] = self.recursive_update(payload, val)
            else:
                payload[key] = val
        return payload

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
