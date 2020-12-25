#!/bin/bash

madconf="../configs/config.ini"
# Grab db info from MAD's config file
! [[ -f "$madconf" ]] && echo "Unable to find your MAD config. You should be running this in the MAD directory" && exit 2
[[ -z "$1" ]] && echo "No CSV file supplied. Usage: $0 CSVfile" && exit 2
dbip=$(awk -F: '/^dbip/{print $2}' "$madconf"|awk -F'#' '{print $1}'|sed -e 's,[[:space:]]*$,,' -e 's,^[[:space:]]*,,')
user=$(awk -F: '/^dbusername/{print $2}' "$madconf"|awk -F'#' '{print $1}'|sed -e 's,[[:space:]]*$,,' -e 's,^[[:space:]]*,,')
pass=$(awk -F: '/^dbpassword/{print $2}' "$madconf"|awk -F'#' '{print $1}'|sed -e 's,[[:space:]]*$,,' -e 's,^[[:space:]]*,,')
dbname=$(awk -F: '/^dbname/{print $2}' "$madconf"|awk -F'#' '{print $1}'|sed -e 's,[[:space:]]*$,,' -e 's,^[[:space:]]*,,')
port=$(awk -F: '/^dbport/{print $2}' "$madconf"|awk -F'#' '{print $1}'|sed -e 's,[[:space:]]*$,,' -e 's,^[[:space:]]*,,')
[[ "$user" == "" ]] && echo "You need to setup the database information in your MAD config before this script can work." && exit 3
[[ "$port" == "" ]] && port=3306

gymCount=0
stopCount=0

while IFS=";" read name url portalGuid
do
 portalGuid=$(sed -e 's,\n,,' -e 's,\r,,' <<< "$portalGuid")
        echo "name: $name, url: $url, external_id: $portalGuid"
        if [ $(mysql -N -s -h "$dbip" -P "$port" -u "$user" -p"${pass}" -D "$dbname" -e "SELECT count(*) from gym where gym_id=\"$portalGuid\";") -eq 1 ]; then
                echo "Thats a gym, updating row..."
        ((gymCount ++))
                mysql -N -s -h "$dbip" -P "$port" -u "$user" -p"${pass}" -D "$dbname" -e "UPDATE gymdetails SET name=\"$name\", url=\"$url\" WHERE gym_id=\"$portalGuid\";"
        else
                echo "Thats NOT a gym, skipping..."
        fi

        if [ $(mysql -N -s -h "$dbip" -P "$port" -u "$user" -p"${pass}" -D "$dbname" -e "SELECT count(*) from pokestop where pokestop_id=\"$portalGuid\";") -eq 1 ]; then
                echo "Thats a pokestop, updating row..."
        ((stopCount ++))
                mysql -N -s -h "$dbip" -P "$port" -u "$user" -p"${pass}" -D "$dbname" -e "UPDATE pokestop SET name=\"$name\", image=\"$url\" WHERE pokestop_id=\"$portalGuid\";"
        else
                echo "Thats NOT a pokestop, skipping..."
        fi

done < "$1"
echo "$gymCount Gyms updated"
echo "$stopCount Stops updated"
