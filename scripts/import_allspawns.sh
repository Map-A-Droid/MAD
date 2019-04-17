#!/bin/bash
########################################################################################################
#   This is the MAD spawnpoint importer. If you used to scan before and happen to still have your
# spawnpoints in your Monocle or Rocketmap database then you can use this script to import them to MAD
# You must have the trs_spawn table already in your database and you must have filled out the Database
# portion of the MAD config file
########################################################################################################
# This section is for your old database, your new database is already configured in MAD/configs/config.ini
# Old database type (only valid options are "rm", "rdm", and "monocle"):
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
! [[ -f "$madconf" ]] && echo "Unable to find your MAD config. You should be running this in the MAD scripts directory or change madconf var" && exit 2
dbip=$(awk -F: '/^dbip/{print $2}' "$madconf"|awk -F'#' '{print $1}'|sed -e 's,[[:space:]]*$,,' -e 's,^[[:space:]]*,,')
user=$(awk -F: '/^dbusername/{print $2}' "$madconf"|awk -F'#' '{print $1}'|sed -e 's,[[:space:]]*$,,' -e 's,^[[:space:]]*,,')
pass=$(awk -F: '/^dbpassword/{print $2}' "$madconf"|awk -F'#' '{print $1}'|sed -e 's,[[:space:]]*$,,' -e 's,^[[:space:]]*,,')
dbname=$(awk -F: '/^dbname/{print $2}' "$madconf"|awk -F'#' '{print $1}'|sed -e 's,[[:space:]]*$,,' -e 's,^[[:space:]]*,,')
port=$(awk -F: '/^dbport/{print $2}' "$madconf"|awk -F'#' '{print $1}'|sed -e 's,[[:space:]]*$,,' -e 's,^[[:space:]]*,,')
[[ "$user" == "" ]] && echo "You need to setup the database information in your MAD config before this script can work." && exit 3
[[ "$port" == "" ]] && port=3306

query(){
mysql -N -B -u "$user" -D "$dbname" -p"$pass" -h "$dbip" -P "$port" -e "$1"
}

oldquery(){
mysql -N -B -u "$olduser" -D "$olddbname" -p"$oldpass" -h "$olddbip" -P "$oldport" -e "$1"
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
 (( "$weirdsql" )) && new="$min:$sec" || new="'$min:$sec'"
fi
}

update_endtime(){
query "update trs_spawn set calc_endminsec=$new where spawnpoint=$spawnpoint;"
echo "spawn $spawn_id endtime updated in the db" >> addspawns.log
}

testweirdsqlupdate(){
 # this function tells me if im dealing with a weird mysql version that doesnt like quoting '12:34' calc_endminsec
if ! [[ "$weirdsql" ]] ;then
 if query "update trs_spawn set calc_endminsec=$new where spawnpoint=$spawnpoint;" 2>/dev/null ;then
  echo "spawn $spawn_id endtime updated in the db" >> addspawns.log
  weirdsql=0
 else
  weirdsql=1
 fi
 if (( "$weirdsql" )) ;then
 # If the above entry failed we have weird sql... now lets run the query again so we dont miss adding this spawnpoint. and if that doesnt work lets quit and get a beer instead
  if query "update trs_spawn set calc_endminsec=${new:1:-1} where spawnpoint=$spawnpoint;" 2>/dev/null ;then
   echo "spawn $spawn_id endtime updated in the db" >> addspawns.log
  else
   echo "neither query style seems to be working, screw this lets get a beer"
   exit 88
  fi
 fi
 return 1 # this will help me skip running the query a second time when im checking for weird sql
fi
return 0  # if weirdsql is already set i can run the query in the import function
}

testweirdsql(){
# same as above but using insert
if ! [[ "$weirdsql" ]] ;then
 if query "insert into trs_spawn set spawnpoint=${spawn_id}, latitude=${lat}, longitude=${lon}, earliest_unseen=99999999, calc_endminsec=$new;" 2>/dev/null ;then
  echo "spawn $spawn_id added to the db" >> addspawns.log
  weirdsql=0
 else
  weirdsql=1
 fi
 if (( "$weirdsql" )) ;then
  if query "insert into trs_spawn set spawnpoint=${spawn_id}, latitude=${lat}, longitude=${lon}, earliest_unseen=99999999, calc_endminsec=${new:1:-1};" 2>/dev/null ;then
   echo "spawn $spawn_id added to the db" >> addspawns.log
  else
   echo "neither query style seems to be working, screw this lets get a beer"
   exit 88
  fi
 fi
 return 1
fi
return 0
}

spawn_exists(){
read -r spawnpoint endtime _ < <(query "select spawnpoint, calc_endminsec from trs_spawn where spawnpoint='$spawn_id'")
if [[ $spawnpoint ]] ;then
   [[ "$endtime" == "NULL" ]] && [[ "$old" != "NULL" ]] && gettime && testweirdsqlupdate && update_endtime && return 69
   echo "spawn $spawn_id already exists in the db" >> addspawns.log && return 69
fi
return 0
}

import_mon(){
while read -r id spawn_id old lat lon updated duration failures _ ;do
 spawn_exists || continue
 gettime
 testweirdsql && query "insert into trs_spawn set spawnpoint=${spawn_id}, latitude=${lat}, longitude=${lon}, earliest_unseen=99999999, calc_endminsec=$new;" && echo "spawn $spawn_id added to the db" >> addspawns.log
done< <(oldquery "select * from spawnpoints")
}

import_rm(){
while read -r spawn_id lat lon _ ;do
 old=$(oldquery "select max(tth_secs) from spawnpointdetectiondata where spawnpoint_id='${spawn_id}';")
 : ${old:="NULL"}
 spawn_exists || continue
 gettime
 testweirdsql && query "insert into trs_spawn set spawnpoint=${spawn_id}, latitude=${lat}, longitude=${lon}, earliest_unseen=99999999, calc_endminsec=$new;" && echo "spawn $spawn_id added to the db" >> addspawns.log
done< <(oldquery "select distinct id, latitude, longitude from spawnpoint" ; oldquery "select distinct id, latitude, longitude from spawnpoint_old" 2>/dev/null)
}

import_rdm(){
while read -r spawn_id lat lon old _ ;do
 spawn_exists || continue
 gettime
 testweirdsql && query "insert into trs_spawn set spawnpoint=${spawn_id}, latitude=${lat}, longitude=${lon}, earliest_unseen=99999999, calc_endminsec=$new;" && echo "spawn $spawn_id added to the db" >> addspawns.log
done< <(oldquery "select id, lat, lon, despawn_sec from spawnpoint")
}

case "$dbtype" in
 monocle) import_mon ;;
      rm) import_rm  ;;
     rdm) import_rdm ;;
       *) echo "unknown dbtype, only valid options are monocle, rdm, and rm... suck it" && exit 4;;
esac
