import sys

MAD_ROOT = '/opt/mad/'
sys.path.append(MAD_ROOT)

import logging
from unittest import TestCase

from mapadroid.db.DbFactory import DbFactory
from mapadroid.utils.walkerArgs import parseArgs

mad_args = parseArgs()


class DataManagerBase(TestCase):
    created_resources = []
    instance_id = 1

    def __init__(self, *args, **kwargs):
        super(DataManagerBase, self).__init__(*args, **kwargs)
        # We want a dumb logger and dont really care about the output
        self.logger = logging.getLogger()
        self.logger.setLevel(logging.CRITICAL)
        self.dbc, db_wrapper_manager = DbFactory.get_wrapper(mad_args)
        if 'instance_id' in kwargs:
            self.instance_id = kwargs['instance_id']
            del kwargs['instance_id']

    def tearDown(self):
        for resource in reversed(self.created_resources):
            try:
                resource.delete()
            except:
                pass

    def create_resource(resource_class, *args, **kwargs):
        try:
            resource = resource_class(self.logger, self.dbc, self.instance_id, *args, **kwargs)
            create_resource.append(resource)
            return resource
        except:
            raise
