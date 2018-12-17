!#/bin/bash
########################################################################################################
#   This is the MAD spawnpoint importer. If you used to scan before and happen to still have your
# spawnpoints in your Monocle or Rocketmap database then you can use this script to import them to MAD
# You must have the trs_spawn table already in your database and you must have filled out the Database
# portion of the MAD config file
########################################################################################################
###################################HAPPY HUNTING ### KRZTHEHUNTER#######################################
########################################################################################################
# You can probably leave this var alone. This is the default config file.
# But if you have a reason that's not the config file you want to use, then go ahead and change
# path to MAD config
madconf="../configs/config.ini"
########################################################################################################

# Grab db info from MAD's config file
! [[ -f "$madconf" ]] && echo "Unable to find your MAD config. You should be running this in the MAD directory" && exit 2
dbtype=$(awk -F: '/^db_method/{print $2}' "$madconf"|awk -F'#' '{print $1}'|sed -e 's,[[:space:]]*$,,' -e 's,^[[:space:]]*,,')
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

import_mon(){
#import spawnpoints
while read -r id spawn_id despawn_time lat lon updated duration failures ;do
 (( $(query "select spawnpoint from trs_spawn where spawnpoint=$spawn_id") )) && echo "spawn $spawn_id already exists in the db" >> addspawns.log && continue
 query "insert into trs_spawn (spawnpoint, latitude, longitude, earliest_unseen) values (${spawn_id}, ${lat}, ${lon}, 99999999);" && echo "spawn $spawn_id added to the db" >> addspawns.log
done< <(query "select * from spawnpoints")

#import endtimes
while read -r spawnpoint old ;do
 min=$(( old / 60))
 sec=$(( old % 60))
 case "$sec" in
  [0-9]) sec="0$sec" ;;
 esac
 new="$min:$sec"
 query "update trs_spawn set calc_endminsec='$new' where spawnpoint=$spawnpoint;"
done < <(query "select spawnpoint, despawn_time from trs_spawn join spawnpoints on trs_spawn.spawnpoint=spawnpoints.spawn_id where calc_endminsec is NULL and despawn_time is not NULL;")
}

#RM
import_rm(){
#import spawnpoints
while read -r spawn_id lat lon _ ;do
 (( $(query "select spawnpoint from trs_spawn where spawnpoint=$spawn_id") )) && echo "spawn $spawn_id already exists in the db" >> addspawns.log && continue
 query "insert into trs_spawn (spawnpoint, latitude, longitude, earliest_unseen) values (${spawn_id}, ${lat}, ${lon}, 99999999);" && echo "spawn $spawn_id added to the db" >> addspawns.log
done< <(query "select * from spawnpoint")

#import endtimes
while read -r spawnpoint old ;do
 min=$(( old / 60))
 sec=$(( old % 60))
 case "$sec" in
  [0-9]) sec="0$sec" ;;
 esac
 new="$min:$sec"
 query "update trs_spawn set calc_endminsec='$new' where spawnpoint=$spawnpoint;"
done < <(query "select spawnpoint, tth_secs from trs_spawn join spawnpointdetectiondata on trs_spawn.spawnpoint=spawnpointdetectiondata.spawnpoint_id where calc_endminsec is NULL and tth_secs is not NULL;")
}

case "$dbtype" in
 monocle) import_mon ;;
      rm) import_rm  ;;
       *) echo "unknown dbmethod set in MAD config file, suck it" && exit 4;;
esac
