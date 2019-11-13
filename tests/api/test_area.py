import copy
from unittest import TestCase
import api_base
import global_variables

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
            "name": "Idle Area",
            "geofence_included": "idle.txt",
            "routecalc": "test_idle"
        }
        headers = {
            'X-Mode': 'idle'
        }
        area = self.create_valid(payload, headers=headers)
        area_uri = area.headers['X-Uri']
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
        errors = {'unknown': ['username']}
        super().invalid_post(payload, errors, headers=headers)
        self.remove_resources()

    def test_valid_post(self):
        headers = {
            'X-Mode': 'raids_mitm'
        }
        results = {
            "name": "UnitTest Area",
            "init": False,
            "geofence_included": "test_geofence.txt",
            "routecalc": "test_routecalc",
            "including_stops": True,
            "settings": {
                "starve_route": False
            },
            "mode": "raids_mitm"
        }
        super().valid_post(self.base_payload, results, headers=headers)
        self.remove_resources()

    def test_walkerarea_dependency(self):
        area_uri = super().create_valid_resource('area')
        walkerarea_uri = super().create_valid_resource('walkerarea', walkerarea=area_uri)
        response = self.delete_resource(area_uri)
        self.assertEqual(response.status_code, 412)

    def test_issue_495(self):
        headers = {
            'X-Mode': 'mon_mitm'
        }
        payload = {
            "geofence_excluded": None,
            "geofence_included": "geofence.txt",
            "name": "UnitTest Area",
            "routecalc": "unittest_area",
            "init": False,
            "coords_spawns_known": False,
            "settings": {
                "starve_route": False,
                "delay_after_prio_event": 1
            }
        }
        response = self.create_valid(payload, headers=headers)
        uri = response.headers['X-Uri']
        patch = {
            'settings': {
                'delay_after_prio_event': None
            }
        }
        response = self.api.patch(uri, json=patch, headers=headers)
        del payload['settings']['delay_after_prio_event']
        del payload['geofence_excluded']
        payload['mode'] = headers['X-Mode']
        response = self.api.get(uri)
        self.assertDictEqual(payload, response.json())
        response = self.delete_resource(uri)
        self.remove_resources()
