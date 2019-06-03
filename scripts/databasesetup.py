import sys
import mysql.connector
import requests
import re

print("Welcome! This script will import the right database schema for you.")

monocle_sql = open('../SQL/monocle.sql')
rm_sql = open('../SQL/rocketmap.sql')
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
    sql_file = rm_sql.read()
else:
    sql_file = monocle_sql.read()

schema = sql_file.splitlines()      
#schema = response.text.readlines()      
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
