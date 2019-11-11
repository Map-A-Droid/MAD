from . import modules
from . import dm_exceptions

# This is still known as the data manager but its more of a Resource Factory.  Its sole purpose is to produce a
# single resource or a list of resources
class DataManager(object):
    def __init__(self, logger, dbc, instance_id):
        self.logger = logger
        self.dbc = dbc
        self.instance_id = instance_id

    def get_resource(self, section, identifier, **kwargs):
        if section == 'area':
            return modules.AreaFactory(self.logger, self.dbc, self.instance_id, identifier=identifier)
        try:
            return modules.MAPPINGS[section](self.logger, self.dbc, self.instance_id, identifier=identifier)
        except KeyError:
            raise dm_exceptions.InvalidSection()

    def get_root_resource(self, section, **kwargs):
        # TODO - Display Field
        fetch_all = kwargs.get('fetch_all', 1)
        mode = kwargs.get('mode', None)
        default_sort = kwargs.get('default_sort', None)
        resource_class = None
        table = None
        primary_key = None
        if section == 'area':
            resource_class = modules.AreaFactory
            table = modules.Area.table
            primary_key = modules.Area.primary_key
        else:
            resource_class = modules.MAPPINGS[section]
            table = resource_class.table
            primary_key = resource_class.primary_key
        sql = 'SELECT `%s` FROM `%s` WHERE `instance_id` = %%s'
        args = [primary_key, table]
        if default_sort:
            sql += ' ORDER BY `%s`'
            args.append(default_sort)
        identifiers = self.dbc.autofetch_column(sql % tuple(args), args=(self.instance_id,))
        data = {}
        for identifier in identifiers:
            data[identifier] = resource_class(self.logger, self.dbc, self.instance_id, identifier=identifier)
        return data