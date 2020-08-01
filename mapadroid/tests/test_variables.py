DEFAULT_OBJECTS = {
    'area': {
        'uri': '/api/area',
        'payload': {
            "geofence_included": "test_geofence.txt",
            "including_stops": True,
            "init": False,
            "name": "%s Area - %s",
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
            'username': 'user - %s',
            'password': 'pass'
        }
    },
    'device': {
        'uri': '/api/device',
        'payload': {
            'origin': '%s Device - %s',
            'settings': {
                'screenshot_type': 'jpeg'
            }
        }
    },
    'devicesetting': {
        'uri': '/api/devicepool',
        'payload': {
            'devicepool': '%s Pool - %s',
            'settings': {
                'screenshot_type': 'jpeg',
                'enhanced_mode_quest': False
            }
        }
    },
    'geofence': {
        'uri': '/api/geofence',
        'payload': {
            'name': '%s Geofence - %s',
            'fence_type': 'polygon',
            'fence_data': []
        }
    },
    'monivlist': {
        'uri': '/api/monivlist',
        'payload': {
            'monlist': '%s MonIVList - %s',
            'mon_ids_iv': []
        }
    },
    'pogoauth': {
        'uri': '/api/pogoauth',
        'payload': {
            'login_type': 'google',
            'username': '%s username - %s',
            'password': 'pass'
        }
    },
    'routecalc': {
        'uri': '/api/routecalc',
        'payload': {
            'routefile': [
                '0,0'
            ]
        }
    },
    'walker': {
        'uri': '/api/walker',
        'payload': {
            'walkername': '%s Walker - %s',
            'setup': [],
        }
    },
    'walkerarea': {
        'uri': '/api/walkerarea',
        'payload': {
            'walkerarea': 'UnitTest WalkerArea',  # This must be populated with a valid area_uri
            'walkertype': 'coords',
            'walkervalue': '',
            'walkermax': '',
            'walkertext': ''
        }
    }
}
