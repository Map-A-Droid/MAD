#!/usr/bin/env python3

import collections
import os
import re
import sys
from typing import List

import mysql.connector

from mapadroid.geofence.geofenceHelper import GeofenceHelper
from mapadroid.utils.logging import init_logging, logger

sys.path.append("..")

configfile = open("../configs/config.ini", "r")
config = configfile.read()


class Args:
    log_level = "DEBUG2"
    verbose = 9
    log_file_level = "CRITICAL"
    no_log_colors = False
    no_file_logs = True


def get_value_for(regex_string, force_exit=True):
    res = re.findall(regex_string, config)
    if res is None or len(res) != 1 or res == []:
        if force_exit:
            if res is None or res == []:
                sys.exit("Check your config.ini for %s - this field is required!" % re.search('\\\s\+(.*):',
                                                                                              regex_string).group(
                    1))
            else:
                sys.exit(
                    "Found more than one value for %s in config.ini, fix that." % re.search('\\\s\+(.*):',
                                                                                            regex_string).group(
                        1))
        return None
    else:
        return res[0]


def main():
    args = Args()
    init_logging(args)

    if len(sys.argv) != 2:
        logger.error("usage: remove_all_spawns_within_geofence.py GEOFENCE_FILENAME")
        sys.exit(1)

    LocationWithID = collections.namedtuple('Location', ['lat', 'lng', 'spawnpoint'])

    geofence_filename = sys.argv[1]
    # print("Argument: '%s'" % (geofence_filename))
    # no .txt, add it
    if ".txt" not in geofence_filename:
        geofence_filename = geofence_filename + ".txt"
    # no / in filename, probably not an absolute path, append standard MAD path
    if "/" not in geofence_filename:
        geofence_filename = "../configs/geofences/" + geofence_filename
    logger.info("Trying to use file: {}", geofence_filename)
    if not os.path.isfile(geofence_filename):
        logger.error("Geofence file {} not found, exit", geofence_filename)
        sys.exit(1)

    geofence_helper = GeofenceHelper(geofence_filename, None)
    minLat, minLon, maxLat, maxLon = geofence_helper.get_polygon_from_fence()
    query = (
        "SELECT latitude, longitude, spawnpoint "
        "FROM trs_spawn "
        "WHERE (latitude >= {} AND longitude >= {} "
        "AND latitude <= {} AND longitude <= {}) "
    ).format(minLat, minLon, maxLat, maxLon)

    delete_query = (
        "DELETE FROM trs_spawn "
        "WHERE spawnpoint = {} "
    )

    list_of_coords: List[LocationWithID] = []

    dbip = get_value_for(r'\s+dbip:\s+([^\s]+)')
    dbport = get_value_for(r'\s+dbport:\s+([^.\s]*)', False)
    if dbport is None:  # if dbport is not set, use default
        dbport = '3306'
    dbusername = get_value_for(r'\s+dbusername:\s+([^.\s]*)')
    dbpassword = get_value_for(r'\s+dbpassword:\s+([^.\s]*)')
    dbname = get_value_for(r'\s+dbname:\s+([^.\s]*)')

    # print("Successfully parsed config.ini, using values:")
    # print("dbport: %s" % dbport)
    # print("dbusername: %s" % dbusername)
    # print("dbname: %s" % dbname)
    # print("dbip: %s" % dbip)

    connection = mysql.connector.connect(
        host=dbip,
        port=dbport,
        user=dbusername,
        passwd=dbpassword,
        database=dbname)
    cursor = connection.cursor()

    cursor.execute(query)
    res = cursor.fetchall()
    for (latitude, longitude, spawnpoint) in res:
        list_of_coords.append(LocationWithID(latitude, longitude, spawnpoint))

    geofenced_coords = geofence_helper.get_geofenced_coordinates(list_of_coords)
    spawnpointcount = len(geofenced_coords)
    for coords in geofenced_coords:
        sql = delete_query.format(coords.spawnpoint)
        cursor.execute(sql)
        # print(sql)

    connection.commit()

    cursor.close()
    connection.close()
    logger.success("Done, deleted {} spawnpoints", spawnpointcount)


if __name__ == "__main__":
    main()
