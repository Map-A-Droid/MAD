#!/bin/bash

# Getting Config Items from User

echo ""
echo "This script will create a new RM DB, create the full schema, and migrate your existing Monocle/RDM data to it".
echo "It will need ROOT access to your DB to be able to perform those tasks"
echo ""
echo -n "IP of your Database ?               "
read dbip
echo -n "Running Port of you Database?       "
read dbport
echo -n "Root Password for your Database ?   "
read -s dbpass

# Checking Connectivity to Database

while ! mysql -h $dbip -P $dbport -u root -p$dbpass  -e ";" ; do
       echo -e "\033[31m"
       echo -n "Cannot connect to DB? Password ?  : "
       echo -ne "\e[0m"
       read dbpass
done

echo -e "\033[32m"
echo "Connection Succesfull... Proceeding"
echo ""
echo -ne "\e[0m"

echo -n "Old schema [rdm/monocle] ?          "
read dbtype
echo -n "Name of your old Database ?         "
read olddbname
echo -n "Name for you new Database ?         "
read newdbname

# Create Query function

query(){
MYSQL_PWD=$dbpass mysql -h $dbip -P $dbport -u root $newdbname -e "$1"
}

DB_CHECK=$(query "SHOW DATABASES;" | grep $newdbname)
if [[ ! -z "${DB_CHECK}" ]]; then
       echo -e "\033[31m"
       echo "Database Already Exist. Cannot Proceed"
       echo ""
       echo -ne "\e[0m"
       exit
fi

echo -e "\033[32m"
echo "Thanks, We got all we need. Starting Migration to $newdbname"
echo ""
echo -ne "\e[0m"

# Creating DB and Schema

echo "Creating New DATABASE..."
MYSQL_PWD=$dbpass mysql -h $dbip -P $dbport -u root -e "CREATE DATABASE $newdbname;"
echo "Creating RM DB Schema..."
MYSQL_PWD=$dbpass mysql -h $dbip -P $dbport -u root $newdbname < SQL/rocketmap.sql

# Start Importing Data

for table in trs_quest trs_spawn trs_spawnsightings trs_status
do
   echo "Importing $table..."
   query "INSERT INTO $table SELECT * FROM $olddbname.$table;"
done

for table in trs_s2cells trs_stats_detect trs_stats_detect_raw trs_stats_location trs_stats_location_raw trs_usage
do
   echo "Creating and Importing $table..."
   query "CREATE TABLE $table LIKE $olddbname.$table;"
   query "INSERT INTO $table SELECT * FROM $olddbname.$table;"
done

if [[ $dbtype == 'monocle' ]]
then

      echo "Importing Gyms from forts..."
      query "INSERT INTO gym (gym_id, latitude, longitude) SELECT external_id, lat, lon from $olddbname.forts;"
      echo "Importing Gymdetails from forts..."
      query "INSERT INTO gymdetails (gym_id, name, url) SELECT external_id, IFNULL(name,''), IFNULL(url,'') from $olddbname.forts;"
      echo "Importing Pokestops..."
      query "INSERT INTO pokestop (pokestop_id, latitude, longitude, name, image) SELECT external_id, lat, lon, name, url from $olddbname.pokestops;"

elif [[ $dbtype == 'rdm' ]]
then

      echo "Importing Gyms from Gym..."
      query "INSERT INTO gym (gym_id, latitude, longitude) SELECT id, lat, lon from $olddbname.gym;"
      echo "Importing Gymdetails from Gym..."
      query "INSERT INTO gymdetails (gym_id, name, url) SELECT id, IFNULL(name,''), IFNULL(url,'') from $olddbname.gym;"
      echo "Importing Pokestops..."
      query "INSERT INTO pokestop (pokestop_id, latitude, longitude, name, image) SELECT id, lat, lon, name, url from $olddbname.pokestop;"

fi

# Last User Interaction

echo -e "\033[32m"
echo "ALL DONE"
echo -e "\033[93m"
echo ""
echo "IMPORTANT : If you were already scanning in MAD using your Monocle database, be sure to remove version.json"
echo "This will let MAD create missing columns on your new RM schema"
echo ""
echo -ne "\e[0m"
