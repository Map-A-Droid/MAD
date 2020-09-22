import copy
from collections import UserDict
import mysql
from ..dm_exceptions import DependencyError, SaveIssue, UnknownIdentifier, UpdateIssue
from ..resource_search import get_search, SearchType
from mapadroid.utils.logging import get_logger, LoggerEnums


logger = get_logger(LoggerEnums.data_manager)


USER_READABLE_ERRORS = {
    str: 'string (MapADroid)',
    int: 'Integer (1,2,3)',
    float: 'Decimal (1.0, 1.5)',
    list: 'Comma-delimited list',
    bool: 'True|False'
}


class ResourceTracker(UserDict):
    def __init__(self, config, data_manager, initialdata={}):
        self.__config = config
        self._data_manager = data_manager
        self.issues = {
            'invalid': [],
            'missing': [],
            'invalid_uri': [],
            'unknown': []
        }
        self.removal = []
        self.completed = False
        super().__init__(initialdata)
        for key, entry in self.__config.items():
            try:
                if entry['settings']['require'] is False:
                    continue
                if key not in initialdata:
                    self.issues['missing'].append(key)
            except KeyError:
                continue

    def __delitem__(self, key):
        """ Removes the key from the dict.  Tracks it in the removal state so it can be correctly set to null """
        try:
            if self.__config[key]['settings']['require'] is True:
                if 'empty' in self.__config[key]['settings']:
                    super().__setitem__(key, self.__config[key]['settings']['empty'])
                else:
                    self.issues['missing'].append(key)
        except KeyError:
            pass
        super().__delitem__(key)
        self.removal.append(key)
        keys = ['invalid', 'invalid_uri', 'unknown']
        for update_key in keys:
            try:
                self.issues[update_key].remove(key)
            except ValueError:
                pass

    def __setitem__(self, key, value):
        """ Just set the value right? :) Perform all validation against the key / value prior to setting
            Validates the format (or converts it).  Raises an exception if it cannot convert the value
            If the field is a resource field, validate all resources are valid
        """
        this_iteration = {
            'invalid': False,
            'invalid_uri': False,
            'missing': False,
            'unknown': False
        }
        if key not in self.__config:
            this_iteration['unknown'] = True
            if key not in self.issues['unknown']:
                self.issues['unknown'].append(key)
            return
        expected = self.__config[key]['settings'].get('expected', str)
        required = self.__config[key]['settings'].get('require', False)
        resource = self.__config[key]['settings'].get('data_source', None)
        try:
            empty = self.__config[key]['settings']['empty']
            has_empty = True
        except KeyError:
            has_empty = False
        if not isinstance(value, expected):
            try:
                if value is None and required is False:
                    pass
                else:
                    try:
                        if expected is list:
                            raise ValueError
                        value = self.format_value(value, expected)
                    except Exception:
                        if has_empty and (value == empty or value is None):
                            if value != empty and value is None:
                                value = empty
                        else:
                            this_iteration['invalid'] = True
                            self.issues['invalid'].append((key, USER_READABLE_ERRORS[expected]))
            except KeyError:
                pass
        try:
            if len(value) == 0 and required:
                if has_empty:
                    value = empty
                else:
                    this_iteration['missing'] = True
                    if key not in self.issues['missing']:
                        self.issues['missing'].append(key)
        except TypeError:
            pass
        # We only want to check sub-resources if we have finished the load from the DB
        if resource and self.completed:
            tmp = value
            if type(value) != list:
                tmp = [value]
            invalid = []
            for identifier in tmp:
                try:
                    self._data_manager.get_resource(resource, identifier=identifier)
                except UnknownIdentifier:
                    invalid.append((key, resource, identifier))
            if invalid:
                this_iteration['invalud_uri'] = True
                if type(value) != list:
                    self.issues['invalid_uri'].append(invalid[0])
                else:
                    self.issues['invalid_uri'].append(invalid)
        super().__setitem__(key, value)
        try:
            self.removal.remove(key)
        except ValueError:
            pass
        keys = ['invalid', 'invalid_uri', 'missing']
        for update_key in keys:
            if update_key in this_iteration and this_iteration[update_key]:
                continue
            try:
                self.issues[update_key].remove(key)
            except ValueError:
                pass

    def format_value(self, value, expected):
        if expected == bool:
            if type(value) is str:
                value = True if value.lower() == "true" else False
            else:
                value = bool(value)
        elif expected == float:
            value = float(value)
        elif expected == int:
            value = int(value)
        elif expected == str:
            value = value.strip()
        return value


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
    # Default name field
    name_field = 'TBD'
    search_field = None

    def __init__(self, data_manager, identifier=None):
        self.identifier = identifier
        self._data_manager = data_manager
        self.instance_id = self._data_manager.instance_id
        self._dbc = self._data_manager.dbc
        self._data = {}
        self._load_defaults()
        if self.identifier is not None:
            try:
                self.identifier = int(self.identifier)
            except (TypeError, ValueError):
                raise UnknownIdentifier()
            self._load()
        else:
            self._default_load()
        self._cleanup_load()

    # All of these are implemented because this is not truely a dict structure but we overload the datasource
    # to act like it is
    def __contains__(self, key):
        return key in self.get_resource()

    def __delitem__(self, key):
        if key in self.configuration['fields']:
            del self._data['fields'][key]
        elif key == 'settings':
            pass
        elif key in self._data['fields'].issues['unknown']:
            self._data['fields'].issues.remove(key)
        else:
            raise KeyError

    def __dict__(self):
        return self.get_resource()

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
        elif 'settings' in self.configuration and key in self.configuration['settings']:
            self._data['settings'][key] = value
        else:
            self._data['fields'].issues['unknown'].append(key)

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
        append = kwargs.get('append', False)
        try:
            del kwargs['append']
        except KeyError:
            append = False
        for update_elems in list(args) + [kwargs]:
            for update_key, update_val in update_elems.items():
                if type(update_val) is dict:
                    self[update_key].update(update_val)
                else:
                    if type(update_val) is list and append:
                        self[update_key] += update_val
                    else:
                        self[update_key] = update_val

    def _cleanup_load(self):
        try:
            del self._data[self.primary_key]
        except KeyError:
            pass
        try:
            del self._data['instance_id']
        except KeyError:
            pass
        fields = ['fields', 'settings']
        for field in fields:
            try:
                self._data[field].completed = True
            except Exception:
                pass

    def _default_load(self):
        pass

    def delete(self):
        if self.identifier is None:
            raise UnknownIdentifier()
        dependencies = self.get_dependencies()
        if dependencies:
            raise DependencyError(dependencies)
        del_data = {
            self.primary_key: self.identifier,
            'instance_id': self.instance_id
        }
        self._dbc.autoexec_delete(self.table, del_data)

    def get_core(self, clear: bool = False):
        if clear:
            data = copy.copy(self.get_resource(backend=True))
        else:
            data = self.get_resource(backend=True)
        try:
            for field, field_value in data['settings'].items():
                data[field] = field_value
            for field in data['settings'].removal:
                data[field] = None
                del self._data['settings'][field]
            data['settings'].removal = []
            del data['settings']
        except KeyError:
            pass
        return data

    def get_dependencies(self):
        return []

    def get_resource(self, backend=False):
        user_data = {}
        fields = self._data['fields']
        if not backend:
            fields = dict(fields)
        user_data.update(fields)
        if 'settings' in self._data:
            settings = self._data['settings']
            if not backend:
                settings = dict(settings)
            user_data['settings'] = settings
        return user_data

    def _load(self):
        query = "SELECT * FROM `%s` WHERE `%s` = %%s AND `instance_id` = %%s" % (self.table, self.primary_key)
        data = self._dbc.autofetch_row(query, args=(self.identifier, self.instance_id))
        if not data:
            raise UnknownIdentifier()
        data = self.translate_keys(data, 'load')
        for field, field_value in data.items():
            if 'settings' in self.configuration and field in self.configuration['settings']:
                if field_value is None:
                    continue
                self._data['settings'][field] = field_value
            elif field in self.configuration['fields']:
                self._data['fields'][field] = field_value

    def _load_defaults(self):
        sections = ['fields', 'settings']
        for section in sections:
            defaults = {}
            try:
                for field, default_value in self.configuration[section].items():
                    try:
                        defaults[field] = default_value['settings']['empty']
                    except KeyError:
                        continue
                self._data[section] = ResourceTracker(copy.deepcopy(self.configuration[section]), self._data_manager,
                                                      initialdata=defaults)
            except KeyError:
                continue
            except TypeError:
                continue

    def presave_validation(self, ignore_issues=[]):
        # Validate required data has been set
        top_levels = ['fields', 'settings']
        issues = {}
        for top_level in top_levels:
            try:
                for issue_section, issue in self._data[top_level].issues.items():
                    if issue_section in ignore_issues:
                        continue
                    if not issue:
                        continue
                    if issue_section not in issues:
                        issues[issue_section] = []
                    issues[issue_section] += issue
            except KeyError:
                continue
        custom_issues = self.validate_custom()
        if custom_issues:
            for key, set_issues in custom_issues.items():
                if key not in issues:
                    issues[key] = set_issues
                elif type(set_issues) is list:
                    issues[key] += set_issues
                elif type(set_issues) is dict:
                    issues[key].update(set_issues)
        if issues:
            logger.warning('Unable to save the resource {} / {}: {}', self.__class__.__name__, self.identifier,
                           issues)
            raise UpdateIssue(**issues)

    def save(self, core_data=None, force_insert=False, ignore_issues=[], **kwargs):
        self.presave_validation(ignore_issues=ignore_issues)
        if core_data is None:
            data = self.get_core(clear=True)
        else:
            data = core_data
        if self.include_instance_id:
            data['instance_id'] = self.instance_id
        data = self.translate_keys(data, 'save')
        if self.identifier:
            data[self.primary_key] = self.identifier
        try:
            if force_insert:
                res = self._dbc.autoexec_insert(self.table, data, optype="ON DUPLICATE", **kwargs)
                if not self.identifier:
                    self.identifier = res
            elif not self.identifier:
                res = self._dbc.autoexec_insert(self.table, data, **kwargs)
                self.identifier = res
            else:
                where = {
                    self.primary_key: self.identifier
                }
                self._dbc.autoexec_update(self.table, data, where_keyvals=where, **kwargs)
        except mysql.connector.Error as err:
            raise SaveIssue(err)
        return self.identifier

    @classmethod
    def search(cls, dbc, res_obj, instance_id, *args, **kwargs):
        sql = "SELECT `%s`\n" \
              "FROM `%s`\n" \
              "WHERE `instance_id` = %%s"
        args = [res_obj.primary_key, res_obj.table, ]
        param_args = [instance_id]
        for search_key, search_value in kwargs.items():
            valid = False
            search_field, search_type = get_search(search_key)
            if search_field in cls.configuration['fields']:
                valid = True
            if search_field in cls.translations:
                search_field = cls.translations[search_field]
                valid = True
            if valid:
                if search_type == SearchType.eq:
                    sql += " AND `%s` = %%s"
                elif search_type == SearchType.like:
                    sql += " AND `%s` LIKE %%s"
                    search_value = "%%{}%%".format(search_value)
                args.append(search_field)
                param_args.append(search_value)
        if res_obj.search_field is not None:
            sql += "\nORDER BY `%s` ASC" % (res_obj.search_field)
        return dbc.autofetch_column(sql % tuple(args), args=tuple(param_args))

    def translate_keys(self, data, operation, translations=None):
        return translate_frontend_names(self, data, operation, translations=translations)

    def validate_custom(self):
        pass


def translate_frontend_names(resource, data, operation, translations=None):
    if translations is None:
        try:
            translations = resource.translations
        except AttributeError:
            return data
    if not translations:
        return data
    if operation == 'load':
        translations = dict(map(reversed, translations.items()))
    translated = {}
    for elem_name, elem_value in data.items():
        try:
            translated[translations[elem_name]] = elem_value
        except KeyError:
            translated[elem_name] = elem_value
    return translated
