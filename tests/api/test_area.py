import copy
from unittest import TestCase
from . import api_base
from . import global_variables

class APIArea(api_base.APITestBase):
    uri = copy.copy(global_variables.DEFAULT_OBJECTS['area']['uri'])
    base_payload = copy.copy(global_variables.DEFAULT_OBJECTS['area']['payload'])

    def test_landing_page(self):
        super().landing_page(test_resource=False)

    def test_landing_page_resource(self):
        headers = {
            'X-Mode': 'idle'
        }
        response = self.api.get(self.uri, headers=headers)
        self.assertEqual(response.status_code, 200)
        json_data = response.json()
        self.assertTrue('resource' in json_data)
        self.assertTrue('results' in json_data)
        self.assertTrue(len(json_data['resource']['fields']) > 0)
        if 'settings' in json_data['resource']:
            self.assertTrue(len(json_data['resource']['settings']) > 0)
        self.remove_resources()

    def test_invalid_uri(self):
        super().invalid_uri()
        self.remove_resources()

    def test_get_modes(self):
        # Create an idle area
        # perform a get against /api/area and verify it comes back
        # perform a get against /api/area?mode=raids_mitm and verify it does not come back
        # perform a get against /api/area/<created_elem> and validate the mode is returned
        payload = {
            "name": "Idle Area - %s",
        }
        headers = {
            'X-Mode': 'idle'
        }
        area = self.create_valid_resource('area', payload=payload, headers=headers)
        area_uri = area['uri']
        res = self.api.get(self.uri)
        resource_resp = 'Please specify a mode for resource information Valid modes: idle,iv_mitm,mon_mitm,pokestops,raids_mitm'
        self.assertEqual(res.json()['resource'], resource_resp)
        self.assertTrue(area_uri in res.json()['results'])
        params = {
            'mode': 'idle'
        }
        res = self.api.get(self.uri, params=params)
        self.assertTrue(area_uri in res.json()['results'])
        params = {
            'mode': 'raids_mitm'
        }
        res = self.api.get(self.uri, params=params)
        self.assertFalse(area_uri in res.json()['results'])
        self.remove_resources()

    def test_invalid_post_mode(self):
        payload = {}
        errors = {'error': 'Please specify a mode for resource information.  Valid modes: idle,iv_mitm,mon_mitm,pokestops,raids_mitm'}
        super().invalid_post(payload, errors, error_code=400)
        headers = {
            'X-Mode': 'fake-mode'
        }
        errors = {'error': 'Invalid mode specified [fake-mode].  Valid modes: idle,iv_mitm,mon_mitm,pokestops,raids_mitm'}
        super().invalid_post(payload, errors, error_code=400, headers=headers)
        self.remove_resources()

    def test_invalid_post(self):
        payload = {
            "geofence_included": "test_geofence.txt",
            "including_stops": True,
            "init": False,
            "name": "UnitTest Area",
            "routecalc": "test_calc",
            "username": "ya",
            "settings": {
                "starve_route": False
            }
        }
        headers = {
            'X-Mode': 'raids_mitm'
        }
        errors = {
            'unknown': ['username'],
            'invalid': [
                ['geofence_included', 'Integer (1,2,3)'],
                ['routecalc', 'Integer (1,2,3)']
            ],
            'invalid_uri': [
                ['geofence_included', 'geofence', 'test_geofence.txt'],
                ['routecalc', 'routecalc', 'test_calc']
            ]
        }
        super().invalid_post(payload, errors, headers=headers)
        self.remove_resources()

    def test_valid_post(self):
        super().create_valid_resource('area')
        self.remove_resources()

    def test_walkerarea_dependency(self):
        walkerarea_obj = super().create_valid_resource('walkerarea')
        response = self.delete_resource(walkerarea_obj['resources']['area']['uri'])
        self.assertEqual(response.status_code, 412)
        self.remove_resources()

    def test_issue_495(self):
        headers = {
            'X-Mode': 'mon_mitm'
        }
        _, payload, headers, elem = super().get_valid_resource('area', headers=headers)
        payload['settings']['delay_after_prio_event'] = 1
        payload['coords_spawns_known'] = False
        del payload['including_stops']
        response = self.create_valid(payload, headers=headers)
        uri = response.headers['X-Uri']
        patch = {
            'settings': {
                'delay_after_prio_event': None
            }
        }
        response = self.api.patch(uri, json=patch, headers=headers)
        del payload['settings']['delay_after_prio_event']
        payload['mode'] = headers['X-Mode']
        response = self.api.get(uri)
        self.remove_resources()
        self.assertDictEqual(payload, response.json())

    def test_recalc(self):
        area_obj = super().create_valid_resource('area')
        self.api.get('/reload')
        recalc_payload = {
            'call': 'recalculate'
        }
        headers = {
            'Content-Type': 'application/json-rpc'
        }
        response = self.api.post(area_obj['uri'], json=recalc_payload, headers=headers)
        self.assertEqual(response.status_code, 204)
        self.remove_resources()