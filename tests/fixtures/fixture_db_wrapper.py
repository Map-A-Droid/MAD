import os
import platform

import pytest
from mysql.connector import connection

from mapadroid.db.DbFactory import DbFactory
from tests.conftest import args


@pytest.fixture(scope='session')
def db_wrapper():
    # Update any walker args that need to be adjusted for this instance
    update_args_testing(args)
    # Prepare the database for the tox env
    create_databases(args)
    # Will be executed before the first test
    db_wrapper, db_pool_manager = DbFactory.get_wrapper(args)
    yield db_wrapper
    # Will be executed after the last test
    db_pool_manager.shutdown()


def get_db_name(ver: str) -> str:
    """ Creates the DB name to use for the version of python """
    return "TOX_MAD_{}".format(ver)


def update_args_testing(launch_args):
    """ Use env vars set from tox / .dev.env """
    ver = platform.python_version()
    launch_args.dbname = get_db_name(ver)
    launch_args.dbip = "mariadb"
    launch_args.dbusername = "root"
    launch_args.dbpassword = os.environ["MYSQL_ROOT_PASSWORD"]


def create_databases(launch_args):
    """ Prep a database for the current tox env """
    cnx = connection.MySQLConnection(user=launch_args.dbusername,
                                     password=launch_args.dbpassword,
                                     host=launch_args.dbip)
    cursor = cnx.cursor()
    cursor.execute("DROP DATABASE IF EXISTS `{}`". format(launch_args.dbname))
    cursor.execute("CREATE DATABASE `{}`".format(launch_args.dbname))
    cnx.commit()
    cnx.close()
