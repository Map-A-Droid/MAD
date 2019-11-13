DEFAULT_OBJECTS = {
    'area': {
        'uri': '/api/area',
        'payload': {
            "geofence_included": "test_geofence.txt",
            "including_stops": True,
            "init": False,
            "name": "UnitTest Area",
            "routecalc": "test_routecalc",
            "settings": {
                "starve_route": False
            }
        },
        'kwargs': {
            'headers': {
                'X-Mode': 'raids_mitm'
            }
        }
    },
    'auth': {
        'uri': '/api/auth',
        'payload': {
            'username': 'user',
            'password': 'pass'
        }
    },
    'device': {
        'uri': '/api/device',
        'payload': {
            'origin': 'UnitTest Device',
            'settings': {
                'screenshot_type': 'jpeg'
            }
        }
    },
    'devicesetting': {
        'uri': '/api/devicepool',
        'payload': {
            'devicepool': 'UnitTest Pool',
            'settings': {
                'screenshot_type': 'jpeg'
            }
        }
    },
    'monivlist': {
        'uri': '/api/monivlist',
        'payload': {
            'monlist': 'Test MonIV List',
            'mon_ids_iv': []
        }
    },
    'walker': {
        'uri': '/api/walker',
        'payload': {
            'walkername': 'UnitTest Walker',
            'setup': [],
        }
    },
    'walkerarea': {
        'uri': '/api/walkerarea',
        'payload': {
            'walkerarea': 'UnitTest WalkerArea', # This must be populated with a valid area_uri
            'walkertype': 'coords',
            'walkervalue': '',
            'walkermax': '',
            'walkertext': ''
        }
    }
}