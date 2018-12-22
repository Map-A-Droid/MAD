#!/bin/bash
########################################################################################################
#   This is the MAD spawnpoint importer. If you used to scan before and happen to still have your
# spawnpoints in your Monocle or Rocketmap database then you can use this script to import them to MAD
# You must have the trs_spawn table already in your database and you must have filled out the Database
# portion of the MAD config file
########################################################################################################
# This section is for your old database, your new database is already configured in MAD/configs/config.ini
# Old database type (only valid options are "rm" and "monocle"):
dbtype=""
# Old database IP:
olddbip="127.0.0.1"
# Old database username:
olduser=""
# Old database pass:
oldpass=""
# Old database name:
olddbname=""
# Old database port:
oldport="3306"
########################################################################################################
# You can probably leave this var alone. This is the default config file.
# But if you have a reason that's not the config file you want to use, then go ahead and change
# path to MAD config
madconf="../configs/config.ini"
########################################################################################################
###################################HAPPY HUNTING#####KRZTHEHUNTER#######################################
########################################################################################################
#                You should not edit below here unless you know what you're doing                      #
########################################################################################################
########################################################################################################


# Grab db info from MAD's config file
! [[ -f "$madconf" ]] && echo "Unable to find your MAD config. You should be running this in the MAD directory" && exit 2
dbip=$(awk -F: '/^dbip/{print $2}' "$madconf"|awk -F'#' '{print $1}'|sed -e 's,[[:space:]]*$,,' -e 's,^[[:space:]]*,,')
user=$(awk -F: '/^dbusername/{print $2}' "$madconf"|awk -F'#' '{print $1}'|sed -e 's,[[:space:]]*$,,' -e 's,^[[:space:]]*,,')
pass=$(awk -F: '/^dbpassword/{print $2}' "$madconf"|awk -F'#' '{print $1}'|sed -e 's,[[:space:]]*$,,' -e 's,^[[:space:]]*,,')
dbname=$(awk -F: '/^dbname/{print $2}' "$madconf"|awk -F'#' '{print $1}'|sed -e 's,[[:space:]]*$,,' -e 's,^[[:space:]]*,,')
port=$(awk -F: '/^dbport/{print $2}' "$madconf"|awk -F'#' '{print $1}'|sed -e 's,[[:space:]]*$,,' -e 's,^[[:space:]]*,,')
[[ "$user" == "" ]] && echo "You need to setup the database information in your MAD config before this script can work." && exit 3
[[ "$port" == "" ]] && port=3306

query(){
/usr/bin/mysql -N -B -u "$user" -D "$dbname" -p"$pass" -h "$dbip" -P "$port" -e "$1"
}

oldquery(){
/usr/bin/mysql -N -B -u "$olduser" -D "$olddbname" -p"$oldpass" -h "$olddbip" -P "$oldport" -e "$1"
}

gettime(){
if [[ "$old" == "NULL" ]] ;then
 new="NULL"
else
 min=$(( old / 60))
 sec=$(( old % 60))
 case "$sec" in
  [0-9]) sec="0$sec" ;;
 esac
 new="'$min:$sec'"
fi
}

update_endtime(){
query "update trs_spawn set calc_endminsec='$new' where spawnpoint=$spawnpoint;"
echo "spawn $spawn_id endtime updated in the db" >> addspawns.log
}

spawn_exists(){
read -r spawnpoint endtime _ < <(query "select spawnpoint, calc_endminsec from trs_spawn where spawnpoint='$spawn_id'")
if [[ $spawnpoint ]] ;then
   [[ "$endtime" == "NULL" ]] && [[ "$old" != "NULL" ]] && gettime && update_endtime && return 69
   echo "spawn $spawn_id already exists in the db" >> addspawns.log && return 69
fi
return 0
}

import_mon(){
while read -r id spawn_id old lat lon updated duration failures _ ;do
 spawn_exists || continue
 gettime
query "insert into trs_spawn set spawnpoint=${spawn_id}, latitude=${lat}, longitude=${lon}, earliest_unseen=99999999, calc_endminsec=$new;" && echo "spawn $spawn_id added to the db" >> addspawns.log
done< <(oldquery "select * from spawnpoints")
}

import_rm(){
while read -r spawn_id lat lon _ ;do
 old=$(oldquery "select max(tth_secs) from spawnpointdetectiondata where spawnpoint_id='${spawn_id}';")
 : ${old:="NULL"}
 spawn_exists || continue
 gettime
query "insert into trs_spawn set spawnpoint=${spawn_id}, latitude=${lat}, longitude=${lon}, earliest_unseen=99999999, calc_endminsec=$new;" && echo "spawn $spawn_id added to the db" >> addspawns.log
done< <(oldquery "select distinct id, latitude, longitude from spawnpoint" ; oldquery "select distinct id, latitude, longitude from spawnpoint_old")
}

case "$dbtype" in
 monocle) import_mon ;;
      rm) import_rm  ;;
       *) echo "unknown dbtype, only valid options are monocle and rm, suck it" && exit 4;;
esac
