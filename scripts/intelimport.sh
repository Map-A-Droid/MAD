#!/bin/bash

madconf="../configs/config.ini"
# Grab db info from MAD's config file
! [[ -f "$madconf" ]] && echo "Unable to find your MAD config. You should be running this in the MAD directory" && exit 2
[[ -z "$1" ]] && echo "No CSV file supplied. Usage: $0 CSVfile" && exit 2
dbtype=$(awk -F: '/^db_method/{print $2}' "$madconf"|awk -F'#' '{print $1}'|sed -e 's,[[:space:]]*$,,' -e 's,^[[:space:]]*,,')
dbip=$(awk -F: '/^dbip/{print $2}' "$madconf"|awk -F'#' '{print $1}'|sed -e 's,[[:space:]]*$,,' -e 's,^[[:space:]]*,,')
user=$(awk -F: '/^dbusername/{print $2}' "$madconf"|awk -F'#' '{print $1}'|sed -e 's,[[:space:]]*$,,' -e 's,^[[:space:]]*,,')
pass=$(awk -F: '/^dbpassword/{print $2}' "$madconf"|awk -F'#' '{print $1}'|sed -e 's,[[:space:]]*$,,' -e 's,^[[:space:]]*,,')
dbname=$(awk -F: '/^dbname/{print $2}' "$madconf"|awk -F'#' '{print $1}'|sed -e 's,[[:space:]]*$,,' -e 's,^[[:space:]]*,,')
port=$(awk -F: '/^dbport/{print $2}' "$madconf"|awk -F'#' '{print $1}'|sed -e 's,[[:space:]]*$,,' -e 's,^[[:space:]]*,,')
[[ "$user" == "" ]] && echo "You need to setup the database information in your MAD config before this script can work." && exit 3
[[ "$port" == "" ]] && port=3306

case "$dbtype" in
 rm)
	gyms="gym"
	gymID="gym_id"
	details="gymdetails"
	pokestopID="pokestop_id"
	pokestopDB="pokestop"
        imgurl="image"
	;;
 *) echo "unknown dbmethod set in MAD config file." && exit 4;;
esac

gymCount=0
stopCount=0

while IFS=";" read name url portalGuid
do
 portalGuid=$(sed -e 's,\n,,' -e 's,\r,,' <<< "$portalGuid")
        echo "name: $name, url: $url, external_id: $portalGuid"
        if [ $(mysql -N -s -h "$dbip" -P "$port" -u "$user" -p"${pass}" -D "$dbname" -e "SELECT count(*) from $gyms where $gymID=\"$portalGuid\";") -eq 1 ]; then
                echo "Thats a gym, updating row..."
        ((gymCount ++))
                mysql -N -s -h "$dbip" -P "$port" -u "$user" -p"${pass}" -D "$dbname" -e "UPDATE $details SET name=\"$name\", url=\"$url\" WHERE $gymID=\"$portalGuid\";"
        else
                echo "Thats NOT a gym, skipping..."
        fi

        if [ $(mysql -N -s -h "$dbip" -P "$port" -u "$user" -p"${pass}" -D "$dbname" -e "SELECT count(*) from $pokestopDB where $pokestopID=\"$portalGuid\";") -eq 1 ]; then
                echo "Thats a pokestop, updating row..."
        ((stopCount ++))
                mysql -N -s -h "$dbip" -P "$port" -u "$user" -p"${pass}" -D "$dbname" -e "UPDATE $pokestopDB SET name=\"$name\", $imgurl=\"$url\" WHERE $pokestopID=\"$portalGuid\";"
        else
                echo "Thats NOT a pokestop, skipping..."
        fi

done < "$1"
echo "$gymCount Gyms updated"
echo "$stopCount Stops updated"
