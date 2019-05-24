import sys
import mysql.connector
from mysql.connector import Error
import urllib.request
import re

print("Welcome! This script will help you setting up a database for MAD and fill in the config correctly.")
db_method = input("Which database schema should be used?\n(monocle or rm) ")
if db_method not in ('rm', 'monocle'):
    sys.exit("Wrong input, use ether \"rm\" or \"monocle\"")

dbip = input("What's the IP adress or hostname of your mysql server? ")
dbport = input("What's the port of your mysql server?\n(the default is 3306) ")
dbusername = input("What's the username of your mysql user for MAD? ")
dbpassword = input("What's the password of the mysql user? ")
dbname = input("What's the name of your mysql database? ")

monocle_url = 'https://raw.githubusercontent.com/whitewillem/PMSF/master/sql/cleandb.sql'
rm_url = 'https://gist.githubusercontent.com/sn0opy/fb654915180cfbd07d5a30407c286995/raw/8467212e1371cc3f6a385e0bc7c3f63daa7a488a/rocketmap-osm-cec.sql'

if db_method in 'rm':
    response = urllib.request.urlopen(rm_url)
else:
    response = urllib.request.urlopen(monocle_url)
data = response.read()      
schema = data.decode('utf-8')

connection = mysql.connector.connect(
        host = dbip,
        user = dbusername,
        passwd = dbpassword,
        database = dbname)
cursor = connection.cursor()
print("\nExecuting SQL schema...")
statement=""
for line in schema:
    if line.strip().startswith('--'):  # ignore sql comment lines
        continue
    if not line.strip().endswith(';'):  # keep appending lines that don't end in ';'
        statement = statement + line
    else:  # when you get a line ending in ';' then exec statement and reset for next statement
        statement = statement + line
        try:
            #cursor.execute(statement)
            print(statement)
            print("next")
        except (OperationalError, ProgrammingError) as e:
            print("\n[WARN] MySQLError during execute statement \n\tArgs: '%s'" % (str(e.args)))

cursor.close()
connection.close()
print("done.")
