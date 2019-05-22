#!/bin/bash
########################################################################################################
# This script will find and delete gyms that have changed to pokestops and pokestops that have         #
# changed to gyms.                                                                                     #
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
dbtype=$(awk -F: '/^db_method/{print $2}' "$madconf"|awk -F'#' '{print $1}'|sed -e 's,[[:space:]]*$,,' -e 's,^[[:space:]]*,,')
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

update_mon(){
while read -r eid ;do     # delete pokestops that are now gyms
 query "delete from pokestops where external_id='$eid'"
 echo "deleted pokestop with external_id $eid"
done < <(query "select g.external_id from forts as g join fort_sightings as f on f.fort_id=g.id join pokestops as p on p.external_id=g.external_id where f.updated > p.updated")
while read -r eid fid ;do # delete gyms that are now pokestops
 query "delete from raids where external_id='$eid'"
 query "delete from fort_sightings where fort_id='$fid'"
 query "delete from forts where external_id='$eid'"
 echo "deleted gym with external_id $eid"
done < <(query "select g.external_id, f.fort_id from forts as g join fort_sightings as f on f.fort_id=g.id join pokestops as p on p.external_id=g.external_id where f.updated < p.updated")
}

update_rm(){
while read -r eid ;do # delete pokestops that are now gyms
 query "delete from pokestop where pokestop_id='$eid'"
 echo "deleted pokestop with external_id $eid"
done < <(query "select pokestop_id from pokestop as p join gym as g on p.pokestop_id=g.gym_id where g.last_scanned > p.last_updated")
while read -r eid ;do # delete gyms that are now pokestops
 query "delete from gym where gym_id='$eid'"
 echo "deleted gym with external_id $eid"
done < <(query "select gym_id from gym as g join pokestop as p on p.pokestop_id=g.gym_id where g.last_scanned < p.last_updated")
}

case "$dbtype" in
 monocle) update_mon ;;
      rm) update_rm  ;;
       *) echo "unknown dbtype, only valid options are monocle and rm, suck it" && exit 4 ;;
esac
