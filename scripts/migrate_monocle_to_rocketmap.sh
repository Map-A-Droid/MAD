#!/bin/bash

########################################################################################################
#   This is the Monocle to Rocketmap migration script. Before you run this you should run              #
# OSM-rocketmap and let it configure its database. After it has built its empty database you can run   #
# this script to populate your rocketmap database with the gym and pokestop info from your monocle     #
# database. Your spawnpoint info is in MAD format so it does not change, but I dump that table from    #
# your monocle db and import it to your rocketmap db for you. I remove all single quotes from gym      #
# names, sorry but not sorry.                                                                          #
########################################################################################################
# Old database, Monocle format:
# Monocle database IP:
olddbip="127.0.0.1"
# Monocle database username:
olduser=""
# Monocle database pass:
oldpass=""
# Monocle database name:
olddbname="Monocle"
# Monocle database port:
oldport="3306"
# new database, Rocketmap format:
# Rocketmap database IP:
newdbip="127.0.0.1"
# Rocketmap database username:
newuser=""
# Rocketmap database pass:
newpass=""
# Rocketmap database name:
newdbname="rocketmap"
# Rocketmap database port:
newport="3306"
########################################################################################################
###################################HAPPY HUNTING#####KRZTHEHUNTER#######################################
########################################################################################################
#                You should not edit below here unless you know what you're doing                      #
########################################################################################################
########################################################################################################

oldquery(){
mysql -NB -h "$olddbip" -u "$olduser" -p"$oldpass" -P "$oldport" "$olddbname" -e "$1"
}
newquery(){
mysql -NB -h "$newdbip" -u "$newuser" -p"$newpass" -P "$newport" "$newdbname" -e "$1"
}

gymquery="select external_id, lat, lon, replace(name,'\'',''), url, park from forts"
stopquery="select external_id, lat, lon, replace(name,'\'',''), url, park from pokestops"

while IFS=';' read -r eid lat lon name url park ;do
 [[ $(newquery "select gym_id from gym where gym_id='$eid'") == "$eid" ]] && continue
 newquery "insert into gym set gym_id='$eid', latitude='$lat', longitude='$lon'" && \
 newquery "insert into gymdetails set gym_id='$eid', name='$name', url='$url'" && \
 [[ "$park" != NULL ]] && [[ "$park" != "0" ]] && newquery "update gym set park='1' where gym_id='$eid'"
done < <(oldquery "$gymquery"|sed 's/\x09/;/g')

while IFS=';' read -r eid lat lon name url ;do
 [[ $(newquery "select pokestop_id from pokestop where pokestop_id='$eid'") == "$eid" ]] && continue
 newquery "insert into pokestop set pokestop_id='$eid', latitude='$lat', longitude='$lon', name='$name', image='$url'"
done < <(oldquery "$stopquery"|sed 's/\x09/;/g')

mysqldump -h "$newdbip" -u "$newuser" -p"$newpass" -P "$newport" "$olddbname" trs_spawn > /tmp/trs_spawn.sql
mysql -NB -h "$newdbip" -u "$newuser" -p"$newpass" -P "$newport" "$newdbname" < /tmp/trs_spawn.sql
