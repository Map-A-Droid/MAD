import sys
py_version = sys.version_info
if py_version.major < 3 or (py_version.major < 3 and py_version.minor < 6):
    print("MAD requires at least python 3.6! Your version: {}.{}"
          .format(py_version.major, py_version.minor))
    sys.exit(1)
from multiprocessing import Process
from typing import Optional

from utils.MappingManager import MappingManager, MappingManagerManager

import calendar
import datetime
import gc
import glob
import os
import time
from threading import Thread, active_count

import psutil

from db.DbFactory import DbFactory
from utils.logging import initLogging, logger
from utils.version import MADVersion
from utils.walkerArgs import parseArgs

args = parseArgs()
os.environ['LANGUAGE'] = args.language
initLogging(args)



db_wrapper, db_wrapper_manager = DbFactory.get_wrapper(args)
version = MADVersion(args, db_wrapper)
version.get_version()


from madmin.madmin import madmin_start
logger.info("Starting Madmin on Port: {}", str(args.madmin_port))
t_madmin = Thread(name="madmin", target=madmin_start,
                  args=(args, db_wrapper, None, None))
t_madmin.daemon = True
t_madmin.start()

try:
    while True:
        time.sleep(10)
except KeyboardInterrupt or Exception:
    logger.info("Shutdown signal received")