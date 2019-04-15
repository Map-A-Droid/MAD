#!/bin/bash

########################################################################################################
#   This is the Monocle/RDM to Rocketmap migration script. Before you run this you should run          #
# OSM-rocketmap and let it configure its database. After it has built its empty database you can run   #
# this script to populate your rocketmap database with the gym and pokestop info from your monocle/RDM #
# database. If you were using Monocle with MAD spawnpoints do not change, so I dump that table from    #
# your monocle db and import it to your rocketmap db for you. If you have old spawnpoint info from     #
# before MAD then you want to use import_allspawns.sh as well. This script does not import things like #
# controlling team/mons, or ex status, because MAD will fill this in after 1 scan. I remove all single #
# quotes from gym names, sorry but not sorry.                                                          #
#                                                                                                      #
# If you get an error like:                                                                            #
#  "ERROR 1364 (HY000) at line 1: Field 'enabled' doesn't have a default value                         #
# Then run this in mysql: SET GLOBAL sql_mode='' and run this script again.                            #
########################################################################################################
# Old database format (valid options: monocle/rdm)
dbtype=""

# Old database, Monocle or RDM format:
# old database IP:
olddbip="127.0.0.1"
# old database username:
olduser=""
# old database pass:
oldpass=""
# old database name:
olddbname=""
# old database port:
oldport="3306"

# new database, Rocketmap format:
# Rocketmap database IP:
newdbip="127.0.0.1"
# Rocketmap database username:
newuser=""
# Rocketmap database pass:
newpass=""
# Rocketmap database name:
newdbname=""
# Rocketmap database port:
newport="3306"
########################################################################################################
###################################HAPPY HUNTING#####KRZTHEHUNTER#######################################
########################################################################################################
#                You should not edit below here unless you know what you're doing                      #
########################################################################################################
########################################################################################################

case "$dbtype" in
 monocle) gymquery="select external_id, lat, lon, replace(name,'\'',''), url, park from forts"
          stopquery="select external_id, lat, lon, replace(name,'\'',''), url from pokestops"
          mysqldump -h "$newdbip" -u "$newuser" -p"$newpass" -P "$newport" "$olddbname" trs_spawn > /tmp/trs_spawn.sql
          mysql -NB -h "$newdbip" -u "$newuser" -p"$newpass" -P "$newport" "$newdbname" < /tmp/trs_spawn.sql
       ;;
     rdm) gymquery="select id, lat, lon, replace(name,'\'',''), url from gym"
          stopquery="select id, lat, lon, replace(name,'\'',''), url from pokestop"
       ;;
       *) echo "you need to configure this script before running it" && exit
       ;;
esac
oldquery(){
mysql -NB -h "$olddbip" -u "$olduser" -p"$oldpass" -P "$oldport" "$olddbname" -e "$1"
}
newquery(){
mysql -NB -h "$newdbip" -u "$newuser" -p"$newpass" -P "$newport" "$newdbname" -e "$1"
}
while IFS=';' read -r eid lat lon name url ;do
 [[ $(newquery "select gym_id from gym where gym_id='$eid'") == "$eid" ]] && continue
 newquery "insert into gym set gym_id='$eid', latitude='$lat', longitude='$lon'" && \
 newquery "insert into gymdetails set gym_id='$eid', name='$name', url='$url'"
done < <(oldquery "$gymquery"|sed 's/\x09/;/g')

while IFS=';' read -r eid lat lon name url ;do
 [[ $(newquery "select pokestop_id from pokestop where pokestop_id='$eid'") == "$eid" ]] && continue
 newquery "insert into pokestop set pokestop_id='$eid', latitude='$lat', longitude='$lon', name='$name', image='$url'"
done < <(oldquery "$stopquery"|sed 's/\x09/;/g')
