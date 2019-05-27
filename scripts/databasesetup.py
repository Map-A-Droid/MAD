import sys
import mysql.connector
import requests
import re

print("Welcome! This script will import the right database schema for you.")

monocle_url = 'https://raw.githubusercontent.com/whitewillem/PMSF/master/sql/cleandb.sql'
rm_url = 'https://gist.githubusercontent.com/sn0opy/fb654915180cfbd07d5a30407c286995/raw/8467212e1371cc3f6a385e0bc7c3f63daa7a488a/rocketmap-osm-cec.sql'
configfile = open("../configs/config.ini", "r")
config = configfile.read()

db_method = re.search(r'db_method:\s*([^.\s]*)',config)
dbip = re.search(r'dbip:\s*([^.\s]*)',config)
dbport = re.search(r'(\#?)dbport:\s*([^.\s]*)',config)
if dbport.group(1): #if dbport is not set, use default
    port = '3306'
else:
    port = dbport.group(2)
dbusername = re.search(r'dbusername:\s*([^.\s]*)',config)
dbpassword = re.search(r'dbpassword:\s*([^.\s]*)',config)
dbname = re.search(r'dbname:\s*([^.\s]*)',config)

print("db_method: ",db_method.group(1))
print("dbport: ",port)
print("dbusername: ",dbusername.group(1))
print("dbname: ",dbname.group(1))

if db_method.group(1) not in ('rm', 'monocle'):
    sys.exit("Wrong db_method in config.ini, use ether \"rm\" or \"monocle\"")
elif db_method.group(1) in 'rm':
    response = requests.get(rm_url)
else:
    response = requests.get(monocle_url)

schema = response.text.splitlines()      
connection = mysql.connector.connect(
        host = dbip.group(1),
        port = port,
        user = dbusername.group(1),
        passwd = dbpassword.group(1),
        database = dbname.group(1))
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
