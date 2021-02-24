#!/bin/bash
########################################################################################################
# This script will truncate the quest table to allow fetching quests again mid-day, say for an event   #
########################################################################################################
#                You should not edit below here unless you know what you're doing                      #
########################################################################################################

# Resolve parent directory of script to include config. This way the script can be run regardless of CWD
PARENT="$(dirname $(readlink -f $0))"
if [ -f "$PARENT/../configs/config.ini" ]; then
  madconf="$PARENT/../configs/config.ini"
else
  >&2 echo "MAD config not found, have you moved the script out of the scripts folder?"
  exit 2
fi

# TODO(artanicus): DB init should be moved to a script library and sourced here instead of a copy in every script
dbip=$(awk -F: '/^dbip/{print $2}' "$madconf"|awk -F'#' '{print $1}'|sed -e 's,[[:space:]]*$,,' -e 's,^[[:space:]]*,,')
user=$(awk -F: '/^dbusername/{print $2}' "$madconf"|awk -F'#' '{print $1}'|sed -e 's,[[:space:]]*$,,' -e 's,^[[:space:]]*,,')
pass=$(awk -F: '/^dbpassword/{print $2}' "$madconf"|awk -F'#' '{print $1}'|sed -e 's,[[:space:]]*$,,' -e 's,^[[:space:]]*,,')
dbname=$(awk -F: '/^dbname/{print $2}' "$madconf"|awk -F'#' '{print $1}'|sed -e 's,[[:space:]]*$,,' -e 's,^[[:space:]]*,,')
port=$(awk -F: '/^dbport/{print $2}' "$madconf"|awk -F'#' '{print $1}'|sed -e 's,[[:space:]]*$,,' -e 's,^[[:space:]]*,,')
[[ "$port" == "" ]] && port=3306

if [[ "$user" == "" ]]; then
  >&2 echo "You need to setup the database information in your MAD config before this script can work."
  exit 3
fi

# TODO(artanicus): DB query function should be in a lib and sourced here
query(){
mysql -N -B -u "$user" -D "$dbname" -p"$pass" -h "$dbip" -P "$port" -e "$1"
}

truncquests(){
  questtable="trs_quest"
  query "$(cat << EOF
TRUNCATE $questtable;
EOF
)"
}

truncquests
