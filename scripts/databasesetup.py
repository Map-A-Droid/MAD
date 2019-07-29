#!/usr/bin/env python3

import sys
import mysql.connector
import requests
import re

monocle_sql = open('../SQL/monocle.sql')
rm_sql = open('../SQL/rocketmap.sql')
configfile = open("../configs/config.ini", "r")
config = configfile.read()

def get_value_for(regex_string, force_exit=True):
    res = re.findall(regex_string, config)
    if res == None or len(res) != 1 or res == []:
         if force_exit:
             # regex for regex, regexception
             if res == None or res == []:
                  sys.exit("Check your config.ini for %s - this field is required!" % re.search('\\\s\+(.*):', regex_string).group(1))
             else:
                  sys.exit("Found more than one value for %s in config.ini, fix that." % re.search('\\\s\+(.*):', regex_string).group(1))
         return None
    else:
         return res[0]

def main():
    print("Welcome! This script will import the right database schema for you.")

    db_method = get_value_for(r'\s+db_method:\s+([^.\s]*)')
    dbip = get_value_for(r'\s+dbip:\s+([^\s]+)')
    dbport = get_value_for(r'\s+dbport:\s+([^.\s]*)', False)
    if dbport == None: #if dbport is not set, use default
        dbport = '3306'
    dbusername = get_value_for(r'\s+dbusername:\s+([^.\s]*)')
    dbpassword = get_value_for(r'\s+dbpassword:\s+([^.\s]*)')
    dbname = get_value_for(r'\s+dbname:\s+([^.\s]*)')

    print("Successfully parsed config.ini, using values:")
    print("db_method: %s" % db_method)
    print("dbport: %s" % dbport)
    print("dbusername: %s" % dbusername)
    print("dbname: %s" % dbname)
    print("dbip: %s" % dbip)

    if db_method not in ('rm', 'monocle'):
        sys.exit("Wrong db_method in config.ini, use ether \"rm\" or \"monocle\"")
    elif db_method in 'rm':
        sql_file = rm_sql.read()
    else:
        sql_file = monocle_sql.read()

    schema = sql_file.splitlines()
    #schema = response.text.readlines()
    connection = mysql.connector.connect(
        host = dbip,
        port = dbport,
        user = dbusername,
        passwd = dbpassword,
        database = dbname)
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
