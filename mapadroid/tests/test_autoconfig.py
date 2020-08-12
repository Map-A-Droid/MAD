import copy
from functools import wraps
from typing import Any
from unittest import TestCase
import xml.etree.ElementTree
import mapadroid.tests.test_variables as global_variables
from mapadroid.tests.test_utils import get_connection_api, get_connection_mitm, ResourceCreator


email_base: str = "UnitTest@UnitTest.com"
pwd_base: str = "base"


def basic_autoconf(func) -> Any:
    @wraps(func)
    def decorated(self, *args, **kwargs):
        api_creator = ResourceCreator(self.api)
        gacct = None
        session_id = None
        try:
            res = self.mitm.post('/autoconfig/register')
            self.assertTrue(res.status_code == 201)
            session_id = res.content.decode('utf-8')
            # Setup basic PD Auth
            payload = {
                'username': email_base,
                'password': pwd_base
            }
            (auth_shared, _) = api_creator.create_valid_resource('auth', payload=payload)
            auth = {
                'mad_auth': auth_shared['uri'].split('/')[-1]
            }
            res = self.api.post('/api/autoconf/pd', json=auth)
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

    def test_workflow_assigned_device(self):
        api_creator = ResourceCreator(self.api)
        gacct = None
        session_id = None
        try:
            res = self.mitm.post('/autoconfig/register')
            self.assertTrue(res.status_code == 201)
            session_id = res.content.decode('utf-8')
            res = self.mitm.get('/autoconfig/{}/status'.format(session_id))
            self.assertTrue(res.status_code == 406)
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
        except Exception:
            raise
        finally:
            api_creator.remove_resources()
            if session_id is not None:
                self.mitm.delete('/autoconfig/{}/complete'.format(session_id))
            if gacct is not None:
                res = self.api.delete(gacct)

    @basic_autoconf
    def test_pd_token_override(self, session_id, dev_info, ss_info, api_creator):
        pwd_sharedsettings: str = "sharedsettings"
        pwd_device: str = "device"
        # Test basic config
        res = self.mitm.get('/autoconfig/{}/pd'.format(session_id))
        self.assertTrue(res.status_code == 200)
        root = xml.etree.ElementTree.fromstring(res.content)
        username = root.find(".//*[@name='user_id']").text
        pwd = root.find(".//*[@name='auth_token']").text
        self.assertTrue(username == email_base)
        self.assertTrue(pwd == pwd_base)
        # Test Shared Setting Config
        update_info = {
            'pool': ss_info['uri']
        }
        res = self.api.patch(dev_info['uri'], json=update_info)
        self.assertTrue(res.status_code == 204)
        update_info = {
            'pd_token_override': pwd_sharedsettings
        }
        res = self.api.patch(dev_info['uri'], json=update_info)
        self.assertTrue(res.status_code == 204)
        res = self.mitm.get('/autoconfig/{}/pd'.format(session_id))
        self.assertTrue(res.status_code == 200)
        root = xml.etree.ElementTree.fromstring(res.content)
        username = root.find(".//*[@name='user_id']").text
        pwd = root.find(".//*[@name='auth_token']").text
        self.assertTrue(username == email_base)
        self.assertTrue(pwd == pwd_sharedsettings)
        # Test Device Config
        update_info = {
            'pd_token_override': pwd_device
        }
        res = self.api.patch(dev_info['uri'], json=update_info)
        self.assertTrue(res.status_code == 204)
        res = self.mitm.get('/autoconfig/{}/pd'.format(session_id))
        self.assertTrue(res.status_code == 200)
        root = xml.etree.ElementTree.fromstring(res.content)
        username = root.find(".//*[@name='user_id']").text
        pwd = root.find(".//*[@name='auth_token']").text
        self.assertTrue(username == email_base)
        self.assertTrue(pwd == pwd_device)
        res = self.mitm.delete('/autoconfig/{}/complete'.format(session_id))
        self.assertTrue(res.status_code == 200)

    @basic_autoconf
    def test_basic_auth_override(self, session_id, dev_info, ss_info, api_creator):
        elem_shared: str = "sharedsettings"
        elem_dev: str = "device"
        payload = {
            'username': elem_shared,
            'password': elem_shared
        }
        (auth_shared, _) = api_creator.create_valid_resource('auth', payload=payload)
        payload = {
            'username': elem_dev,
            'password': elem_dev
        }
        (auth_dev, _) = api_creator.create_valid_resource('auth', payload=payload)
        # Test basic config
        res = self.mitm.get('/autoconfig/{}/pd'.format(session_id))
        self.assertTrue(res.status_code == 200)
        root = xml.etree.ElementTree.fromstring(res.content)
        username = root.find(".//*[@name='auth_username']").text
        pwd = root.find(".//*[@name='auth_password']").text
        self.assertTrue(username == email_base)
        self.assertTrue(pwd == pwd_base)
        # Test Shared Setting Config
        update_info = {
            'pool': ss_info['uri']
        }
        res = self.api.patch(dev_info['uri'], json=update_info)
        self.assertTrue(res.status_code == 204)
        update_info = {
            'basic_auth_override': auth_shared['uri']
        }
        res = self.api.patch(ss_info['uri'], json=update_info)
        self.assertTrue(res.status_code == 204)
        res = self.mitm.get('/autoconfig/{}/pd'.format(session_id))
        self.assertTrue(res.status_code == 200)
        root = xml.etree.ElementTree.fromstring(res.content)
        username = root.find(".//*[@name='auth_username']").text
        pwd = root.find(".//*[@name='auth_password']").text
        self.assertTrue(username == elem_shared)
        self.assertTrue(pwd == elem_shared)
        # Test Device Config
        update_info = {
            'basic_auth_override': auth_dev['uri']
        }
        res = self.api.patch(dev_info['uri'], json=update_info)
        self.assertTrue(res.status_code == 204)
        res = self.mitm.get('/autoconfig/{}/pd'.format(session_id))
        self.assertTrue(res.status_code == 200)
        root = xml.etree.ElementTree.fromstring(res.content)
        username = root.find(".//*[@name='auth_username']").text
        pwd = root.find(".//*[@name='auth_password']").text
        self.assertTrue(username == elem_dev)
        self.assertTrue(pwd == elem_dev)
        res = self.mitm.delete('/autoconfig/{}/complete'.format(session_id))
        self.assertTrue(res.status_code == 200)
