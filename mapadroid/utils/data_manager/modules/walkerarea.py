from . import resource


class WalkerArea(resource.Resource):
    table = 'settings_walkerarea'
    name_field = 'walkertext'
    primary_key = 'walkerarea_id'
    search_field = 'name'
    translations = {
        'walkerarea': 'area_id',
        'walkertype': 'algo_type',
        'walkervalue': 'algo_value',
        'walkermax': 'max_walkers',
        'walkertext': 'name'
    }
    configuration = {
        "fields": {
            "walkerarea": {
                "settings": {
                    "type": "text",
                    "require": True,
                    "description": "Configured area for the walkerarea",
                    "expected": int,
                    "uri": True,
                    "data_source": "area",
                    "uri_source": "api_area"
                }
            },
            "walkertype": {
                "settings": {
                    "type": "text",
                    "require": True,
                    "description": "Mode for the walker",
                    "expected": str
                }
            },
            "walkervalue": {
                "settings": {
                    "type": "text",
                    "require": True,
                    "empty": "",
                    "description": "Value for walkermode.  Please see above how to configure value",
                    "expected": str
                }
            },
            "walkermax": {
                "settings": {
                    "type": "text",
                    "require": False,
                    "empty": "",
                    "description": "Number of walkers than can be in the area.  Empty = 1 worker (Default: Empty)",
                    "expected": int
                }
            },
            "walkertext": {
                "settings": {
                    "type": "text",
                    "require": False,
                    "empty": "",
                    "description": "Human-readable description of the walkerarea",
                    "expected": str
                }
            }
        }
    }

    def get_dependencies(self):
        sql = 'SELECT `walker_id` FROM `settings_walker_to_walkerarea` WHERE `walkerarea_id` = %s'
        dependencies = self._dbc.autofetch_column(sql, args=(self.identifier,))
        for ind, walkerarea_id in enumerate(dependencies[:]):
            dependencies[ind] = ('walker', walkerarea_id)
        return dependencies

    def _load(self):
        super()._load()
        try:
            if self._data['fields']['walkermax'] == None:
                self._data['fields']['walkermax'] = ''
        except KeyError:
            self._data['fields']['walkermax'] = ''

    def save(self, force_insert=False, ignore_issues=[]):
        self.presave_validation(ignore_issues=ignore_issues)
        try:
            if self._data['fields']['walkermax'] == '':
                core_data = self.get_resource(backend=True)
                core_data['walkermax'] = None
                super().save(core_data=core_data, force_insert=force_insert, ignore_issues=ignore_issues)
            else:
                super().save(force_insert=force_insert, ignore_issues=ignore_issues)
        except KeyError:
            super().save()
