#!/usr/bin/env python3

import re
import sys

import mysql.connector

rm_sql = open('SQL/rocketmap.sql')
configfile = open("../configs/config.ini", "r")
config = configfile.read()


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
    print("Welcome! This script will import the right database schema for you.")

    dbip = get_value_for(r'\s+dbip:\s+([^\s]+)')
    dbport = get_value_for(r'\s+dbport:\s+([^.\s]*)', False)
    if dbport is None:  # if dbport is not set, use default
        dbport = '3306'
    dbusername = get_value_for(r'\s+dbusername:\s+([^.\s]*)')
    dbpassword = get_value_for(r'\s+dbpassword:\s+([^.\s]*)')
    dbname = get_value_for(r'\s+dbname:\s+([^.\s]*)')

    print("Successfully parsed config.ini, using values:")
    print("dbport: %s" % dbport)
    print("dbusername: %s" % dbusername)
    print("dbname: %s" % dbname)
    print("dbip: %s" % dbip)

    sql_file = rm_sql.read()

    schema = sql_file.splitlines()
    # schema = response.text.readlines()
    connection = mysql.connector.connect(
        host=dbip,
        port=dbport,
        user=dbusername,
        passwd=dbpassword,
        database=dbname)
    cursor = connection.cursor()
    print("\nExecuting SQL schema...")
    statement = ''
    for line in schema:
        if line.strip().startswith('--'):  # ignore sql comment lines
            continue
        if not line.strip().endswith(';'):  # keep appending lines that don't end in ';'
            statement = statement + line
        else:  # when you get a line ending in ';' then exec statement and reset for next statement
            statement = statement + line
            cursor.execute(statement)
            statement = ''

    cursor.close()
    connection.close()
    print("Done.")


if __name__ == "__main__":
    main()
