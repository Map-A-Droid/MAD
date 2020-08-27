import copy
from functools import wraps
import json
from typing import Any
from unittest import TestCase
import mapadroid.tests.test_variables as global_variables
from mapadroid.tests.test_utils import get_connection_api, get_connection_mitm, ResourceCreator, GetStorage
from mapadroid.utils.walkerArgs import parse_args
from mapadroid.utils.autoconfig import AutoConfIssues


args = parse_args()
email_base: str = "UnitTest@UnitTest.com"
pwd_base: str = "base"
pd_host = 'http://1.1.1.69:8000'
pd_conf = {
    'post_destination': pd_host
}
rgc_host = 'ws://192.168.1.69:8080'
rgc_conf = {
    'websocket_uri': rgc_host
}


def create_valid_configs(test_obj, api_creator, auth: bool = True, pd_conf: dict = pd_conf, rgc_conf: dict = rgc_conf):
    conf_pd = copy.deepcopy(pd_conf)
    conf_rgc = copy.deepcopy(rgc_conf)
    if auth:
        payload = {
            'username': email_base,
            'password': pwd_base
        }
        (auth_shared, _) = api_creator.create_valid_resource('auth', payload=payload)
        conf_pd['mad_auth'] = auth_shared['uri'].split('/')[-1]
        conf_rgc['mad_auth'] = auth_shared['uri'].split('/')[-1]
    res = test_obj.api.post('/api/autoconf/pd', json=conf_pd)
    test_obj.assertTrue(res.status_code == 200)
    res = test_obj.api.post('/api/autoconf/rgc', json=conf_rgc)
    test_obj.assertTrue(res.status_code == 200)


def basic_autoconf(func) -> Any:
    @wraps(func)
    def decorated(self, *args, **kwargs):
        api_creator = ResourceCreator(self.api)
        gacct = None
        session_id = None
        with GetStorage(self.api) as storage:
            try:
                storage.upload_all()
                create_valid_configs(self, api_creator)
                res = self.mitm.post('/autoconfig/register')
                self.assertTrue(res.status_code == 201)
                session_id = res.content.decode('utf-8')
                # Create Google Account
                gacc = {
                    "login_type": "google",
                    "username": "Unit",
                    "password": "Test"
                }
                res = self.api.post('/api/pogoauth', json=gacc)
                gacct = res.headers['X-URI']
                self.assertTrue(res.status_code == 201)
                dev_payload = copy.copy(global_variables.DEFAULT_OBJECTS['device']['payload'])
                dev_payload['account_id'] = gacct
                (dev_info, _) = api_creator.create_valid_resource('device', payload=dev_payload)
                accept_info = {
                    'status': 1,
                    'device_id': dev_info['uri']
                }
                res = self.api.post('/api/autoconf/{}'.format(session_id), json=accept_info)
                self.assertTrue(res.status_code == 200)
                res = self.mitm.get('/autoconfig/{}/status'.format(session_id))
                self.assertTrue(res.status_code == 200)
                (ss_info, _) = api_creator.create_valid_resource('devicesetting')
                func(self, session_id, dev_info, ss_info, api_creator, *args, **kwargs)
            except Exception:
                raise
            finally:
                self.api.delete('/api/autoconf/rgc')
                self.api.delete('/api/autoconf/pd')
                api_creator.remove_resources()
                if session_id is not None:
                    self.mitm.delete('/autoconfig/{}/complete'.format(session_id))
                if gacct is not None:
                    self.api.delete(gacct)
    return decorated


class MITMAutoConf(TestCase):
    def setUp(self):
        self.api = get_connection_api()
        self.mitm = get_connection_mitm(self.api)

    def tearDown(self):
        self.api.close()
        self.mitm.close()

    def test_no_auth(self):
        # Remove any existing auth
        auths = self.api.get('/api/auth').json()
        for auth_id, _ in auths.items():
            self.api.delete('/api/auth/{}'.format(auth_id))
        res = self.mitm.get('/autoconfig/0/status')
        self.assertTrue(res.status_code == 404)
        res = self.mitm.post('/autoconfig/register')
        self.assertTrue(res.status_code == 201)
        session_id = res.content.decode('utf-8')
        res = self.mitm.delete('/autoconfig/{}/complete'.format(session_id))
        self.assertTrue(res.status_code == 200)

    def test_no_configured_endpoints(self):
        api_creator = ResourceCreator(self.api)
        session_id = None
        try:
            res = self.mitm.post('/autoconfig/register')
            self.assertTrue(res.status_code == 201)
            session_id = res.content.decode('utf-8')
            (dev_info, _) = api_creator.create_valid_resource('device')
            accept_info = {
                'status': 1,
                'device_id': dev_info['uri']
            }
            with GetStorage(self.api) as storage:
                storage.upload_all()
                res = self.api.post('/api/autoconf/{}'.format(session_id), json=accept_info)
                self.assertTrue(res.status_code == 406)
                expected_issues = {
                    'X-Critical': [
                        AutoConfIssues.pd_not_configured.value,
                        AutoConfIssues.rgc_not_configured.value,
                    ],
                    'X-Warnings': [
                        AutoConfIssues.no_ggl_login.value,
                        AutoConfIssues.auth_not_configured.value,
                    ]
                }
                self.assertListEqual(expected_issues['X-Critical'], json.loads(res.headers['X-Critical']))
                self.assertListEqual(expected_issues['X-Warnings'], json.loads(res.headers['X-Warnings']))
        finally:
            api_creator.remove_resources()
            if session_id is not None:
                self.mitm.delete('/autoconfig/{}/complete'.format(session_id))

    def test_missing_apks(self):
        api_creator = ResourceCreator(self.api)
        session_id = None
        try:
            res = self.mitm.post('/autoconfig/register')
            self.assertTrue(res.status_code == 201)
            session_id = res.content.decode('utf-8')
            (dev_info, _) = api_creator.create_valid_resource('device')
            accept_info = {
                'status': 1,
                'device_id': dev_info['uri']
            }
            with GetStorage(self.api) as storage:
                res = self.api.post('/api/autoconf/{}'.format(session_id), json=accept_info)
                self.assertTrue(res.status_code == 406)
                expected_issues = {
                    'X-Critical': [
                        AutoConfIssues.pd_not_configured.value,
                        AutoConfIssues.rgc_not_configured.value,
                        AutoConfIssues.package_missing.value,
                    ],
                    'X-Warnings': [
                        AutoConfIssues.no_ggl_login.value,
                        AutoConfIssues.auth_not_configured.value,
                    ]
                }
                self.assertListEqual(expected_issues['X-Critical'], json.loads(res.headers['X-Critical']))
                self.assertListEqual(expected_issues['X-Warnings'], json.loads(res.headers['X-Warnings']))
                storage.upload_rgc()
                res = self.api.post('/api/autoconf/{}'.format(session_id), json=accept_info)
                self.assertTrue(res.status_code == 406)
                expected_issues = {
                    'X-Critical': [
                        AutoConfIssues.pd_not_configured.value,
                        AutoConfIssues.rgc_not_configured.value,
                        AutoConfIssues.package_missing.value,
                    ],
                    'X-Warnings': [
                        AutoConfIssues.no_ggl_login.value,
                        AutoConfIssues.auth_not_configured.value,
                    ]
                }
                self.assertListEqual(expected_issues['X-Critical'], json.loads(res.headers['X-Critical']))
                self.assertListEqual(expected_issues['X-Warnings'], json.loads(res.headers['X-Warnings']))
                storage.upload_pd()
                res = self.api.post('/api/autoconf/{}'.format(session_id), json=accept_info)
                self.assertTrue(res.status_code == 406)
                expected_issues = {
                    'X-Critical': [
                        AutoConfIssues.pd_not_configured.value,
                        AutoConfIssues.rgc_not_configured.value,
                        AutoConfIssues.package_missing.value,
                    ],
                    'X-Warnings': [
                        AutoConfIssues.no_ggl_login.value,
                        AutoConfIssues.auth_not_configured.value,
                    ]
                }
                self.assertListEqual(expected_issues['X-Critical'], json.loads(res.headers['X-Critical']))
                self.assertListEqual(expected_issues['X-Warnings'], json.loads(res.headers['X-Warnings']))
                storage.upload_pogo()
                res = self.api.post('/api/autoconf/{}'.format(session_id), json=accept_info)
                self.assertTrue(res.status_code == 406)
                expected_issues = {
                    'X-Critical': [
                        AutoConfIssues.pd_not_configured.value,
                        AutoConfIssues.rgc_not_configured.value,
                    ],
                    'X-Warnings': [
                        AutoConfIssues.no_ggl_login.value,
                        AutoConfIssues.auth_not_configured.value,
                    ]
                }
                self.assertListEqual(expected_issues['X-Critical'], json.loads(res.headers['X-Critical']))
                self.assertListEqual(expected_issues['X-Warnings'], json.loads(res.headers['X-Warnings']))
        finally:
            api_creator.remove_resources()
            if session_id is not None:
                self.mitm.delete('/autoconfig/{}/complete'.format(session_id))

    def test_autoconfig_file_download(self):
        api_creator = ResourceCreator(self.api)
        with GetStorage(self.api) as storage:
            try:
                # this really isnt an api call but whatever
                res = self.api.get('/autoconfig/download')
                self.assertTrue(res.status_code == 406)
                # Setup default env without anything defined
                create_valid_configs(self, api_creator, auth=False)
                storage.upload_all()
                res = self.api.get('/autoconfig/download')
                self.assertTrue(res.status_code == 200)
                self.assertTrue(pd_host == res.content.decode('utf-8'))
                create_valid_configs(self, api_creator)
                res = self.api.get('/autoconfig/download')
                self.assertTrue(res.status_code == 200)
                auth = f"{email_base}:{pwd_base}"
                expected = f"{pd_host}\n{auth}"
                self.assertTrue(expected == res.content.decode('utf-8'))
            except Exception:
                raise
            finally:
                rgc_delete = self.api.delete('/api/autoconf/rgc')
                pd_delete = self.api.delete('/api/autoconf/pd')
                api_creator.remove_resources()
                self.assertTrue(rgc_delete.status_code == 200)
                self.assertTrue(pd_delete.status_code == 200)

    @basic_autoconf
    def test_workflow_assigned_device(self, session_id, dev_info, ss_info, api_creator):
        res = self.mitm.get('/autoconfig/{}/status'.format(session_id))
        self.assertTrue(res.status_code == 200)
        data = '2,UnitTest Log Message'
        res = self.mitm.post('/autoconfig/{}/log'.format(session_id), data=data)
        self.assertTrue(res.status_code == 201)
        res = self.mitm.get('/autoconfig/{}/pd'.format(session_id))
        self.assertTrue(res.status_code == 200)
        res = self.mitm.get('/autoconfig/{}/rgc'.format(session_id))
        self.assertTrue(res.status_code == 200)
        res = self.mitm.get('/autoconfig/{}/google'.format(session_id))
        self.assertTrue(res.status_code == 200)
        self.assertTrue(res.content == b'Unit\nTest')
        res = self.mitm.delete('/autoconfig/{}/complete'.format(session_id))
        self.assertTrue(res.status_code == 200)
