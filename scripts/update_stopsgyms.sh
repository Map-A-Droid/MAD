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

updategyminfo(){
#update name/image for gyms that were pokestops (pokestops scan this info automagically, gyms dont)
# thanks to TiMXL73 for the query / idea
query "$(cat << EOF
UPDATE $gymtable
SET $gymtable.name =
IF(
  (SELECT name FROM $pstable WHERE $pstable.$psidcol = $gymtable.$gymidcol) IS NULL,
  '$namedefault',
  (SELECT name FROM $pstable WHERE $pstable.$psidcol = $gymtable.$gymidcol)
)
WHERE $gymtable.name = '$namedefault';
EOF
)"
query "$(cat << EOF
UPDATE $gymtable
SET $gymtable.url =
IF(
  (SELECT $psurlcol FROM $pstable WHERE $pstable.$psidcol = $gymtable.$gymidcol) IS NULL,
  '',
  (SELECT $psurlcol FROM $pstable WHERE $pstable.$psidcol = $gymtable.$gymidcol)
)
WHERE $gymtable.url = '';
EOF
)"
}

update_mon(){
gymtable=forts
pstable=pokestops
psidcol=external_id
gymidcol=external_id
unset namedefault
psurlcol=url
updategyminfo
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
gymtable=gymdetails
pstable=pokestop
psidcol=pokestop_id
gymidcol=gym_id
namedefault=unknown
psurlcol=image
updategyminfo
while read -r eid ;do # delete pokestops that are now gyms
 query "delete from pokestop where pokestop_id='$eid'"
 echo "deleted pokestop with external_id $eid"
done < <(query "select pokestop_id from pokestop as p join gym as g on p.pokestop_id=g.gym_id where g.last_scanned > p.last_updated")
while read -r eid ;do # delete gyms that are now pokestops
 query "delete from gym where gym_id='$eid'"
 echo "deleted gym with external_id $eid"
done < <(query "select gym_id from gym as g join pokestop as p on p.pokestop_id=g.gym_id where g.last_scanned < p.last_updated")
}

update_rm
