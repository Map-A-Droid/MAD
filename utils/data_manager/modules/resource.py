from .. import dm_exceptions
from collections import UserDict
import copy

class ResourceTracker(UserDict):
    def __init__(self, config, initialdata={}):
        self.__config = config
        super().__init__(initialdata)

    removal = []
    def __delitem__(self, key):
        try:
            if self.__config[key]['settings']['require'] == True:
                if 'empty' in self.__config[key]['settings']:
                    super().__setitem__(key, self.__config[key]['settings']['empty'])
                else:
                    raise dm_exceptions.RequiredFieldRemoved()
        except KeyError:
            pass
        super().__delitem__(key)
        self.removal.append(key)

    def __setitem__(self, key, val):
        # TODO - Validate incoming IDs
        if key not in self.__config:
            raise KeyError
        expected = self.__config[key]['settings'].get('expected', str)
        required = self.__config[key]['settings'].get('require', False)
        try:
            empty = self.__config[key]['settings']['empty']
            has_empty = True
        except:
            has_empty = False
        if not isinstance(val, expected):
            try:
                if val is None and required == False:
                    pass
                else:
                    try:
                        val = expected(val)
                    except:
                        if has_empty and val == empty:
                            pass
                        else:
                            raise dm_exceptions.InvalidDataFormat(key, val, expected)
            except KeyError:
                pass
        super().__setitem__(key, val)
        try:
            self.removal.remove(key)
        except:
            pass

class Resource(object):
    # Name of the table within the database
    table = None
    # Primary key for accessing the object
    primary_key = None
    # Include instance_id during saving
    include_instance_id = True
    # Translations from backend names to frontend names
    translations = {}
    # Configuration for converting from table to class
    configuration = None

    def __init__(self, logger, dbc, instance, identifier=None):
        self._logger = logger
        self._dbc = dbc
        self.identifier = int(identifier)
        self.instance_id = instance
        self._data = {}
        self.__load_defaults()
        if self.identifier is not None:
            self._load()

    def __contains__(self, key):
        return key in self.get_resource()

    def __delitem__(self, key):
        if key in self.configuration['fields']:
            del self._data['fields'][key]
        elif key == 'settings':
            pass
        else:
            raise KeyError

    def __getitem__(self, key):
        if key in self.configuration['fields']:
            return self._data['fields'][key]
        elif 'settings' in self.configuration and key == 'settings':
            return self._data['settings']
        else:
            raise KeyError

    def __setitem__(self, key, value):
        if key in self.configuration['fields']:
            self._data['fields'][key] = value
        elif key == 'settings':
            pass
        else:
            raise KeyError

    def __iter__(self):
        return iter(self.get_resource())

    def __len__(self):
        return len(self.get_resource())

    def __keytransform__(self, key):
        return key

    def __str__(self):
        return str(self.get_resource())

    def get(self, key, default):
        return self.get_resource().get(key, default)

    def items(self):
        return self.get_resource().items()

    def keys(self):
        return self.get_resource().keys()

    def update(self, *args, **kwargs):
        for d in list(args) + [kwargs]:
            for k,v in d.items():
                if type(v) is dict:
                    self[k] = self[k].update(v)
                else:
                    self[k]=v

    def _cleanup_load(self):
        try:
            del self._data[self.primary_key]
        except:
            pass
        try:
            del self._data['instance_id']
        except:
            pass

    def delete(self):
        if self.identifier is None:
            raise dm_exceptions.UnknownIdentifier()
        dependencies = self.get_dependencies()
        if dependencies:
            raise dm_exceptions.DependencyError(dependencies)
        del_data = {
            self.primary_key: self.identifier,
            'instance_id': self.instance_id
        }
        self._dbc.autoexec_delete(self.table, del_data)

    def get_dependencies(self):
        return []

    def get_resource(self):
        if self.identifier is not None:
            user_data = {}
            user_data.update(dict(self._data['fields']))
            if 'settings' in self._data:
                user_data['settings'] = dict(self._data['settings'])
            return user_data
        else:
            raise dm_exceptions.IdentifierNotSpecified()

    def _load(self):
        query = "SELECT * FROM `%s` WHERE `%s` = %%s AND `instance_id` = %%s" % (self.table, self.primary_key)
        data = self._dbc.autofetch_row(query, args=(self.identifier, self.instance_id))
        if not data:
            raise dm_exceptions.UnknownIdentifier()
        data = self.translate_keys(data, 'load')
        for field, val in data.items():
            if 'settings' in self.configuration and field in self.configuration['settings']:
                if val is None:
                    continue
                self._data['settings'][field] = val
            elif field in self.configuration['fields']:
                self._data['fields'][field] = val
        self._cleanup_load()

    def __load_defaults(self):
        sections = ['fields', 'settings']
        for section in sections:
            defaults = {}
            try:
                for field, val in self.configuration[section].items():
                    try:
                        val['settings']['require'] == True and val['settings']['empty']
                        defaults[field] = val['settings']['empty']
                    except:
                        continue
                self._data[section] = ResourceTracker(self.configuration[section], defaults)
            except KeyError:
                continue
            except TypeError:
                continue
    def save(self, core_data=None):
        if core_data is None:
            data = self.get_resource()
        else:
            data = core_data
        if self.include_instance_id:
            data['instance_id'] = self.instance_id
        if self.identifier is not None:
            data[self.primary_key] = int(self.identifier)
        try:
            for field, val in data['settings'].items():
                data[field] = val
            for field in data['settings'].removal:
                data[field] = None
                del self._data['settings'][field]
            data['settings'].removal = []
            del data['settings']
        except:
            pass
        data = self.translate_keys(data, 'save')
        res = self._dbc.autoexec_insert(self.table, data, optype="ON DUPLICATE")
        return res

    def translate_keys(self, data, operation, translations=None):
        if translations is None:
            translations = self.translations
        if not translations:
            return data
        if operation == 'load':
            translations = dict(map(reversed, translations.items()))
        for key, val in data.items():
            new_key = key
            if key in translations:
                new_key = translations[key]
                data[new_key] = val
                del data[key]
        return data
