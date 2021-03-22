#!/bin/bash
#DONT FORGETT  sed -i -e 's/\r$//' scan.sh
#Add  execution rights to file 777
#MAD Script
#Control scan MAD
#Start, Stop and Status exemples
#./scan.bash start
#./scan.bash stop
#./scan.bash status


DAEMON_NAME="Choose a Name"  # Choose a short Name
WORKDIR="/Home/User/MAD"  #Here full directory of MAD
CMD="PYTHONIOENCODING=utf-8 python3 start.py -os"
USER=root
PIDFILE=/var/run/daemonname.pid


daemon_status(){
  start-stop-daemon --status --quiet --pidfile $PIDFILE
}

start(){
 start-stop-daemon --start --pidfile $PIDFILE -b -m --chdir $WORKDIR --exec /usr/bin/sudo -- -u $USER $CMD
 sleep 2
 daemon_status
 if [ $? -eq 0 ]; then
   echo "$DAEMON_NAME started ok"
 else
   echo "$DAEMON_NAME start failed"
fi
}

stop(){
 start-stop-daemon --stop --quiet --oknodo --pidfile $PIDFILE
 RET=$?
 if [ $RET -eq 0 ]; then
   rm -f $PIDFILE
   echo "$DAEMON_NAME stopped"
 else
   echo "$DAEMON_NAME stopping failed"
 fi
}



status(){
 daemon_status
 if [ $? -eq 0 ]; then
   echo "$DAEMON_NAME is running"
 else
   echo "$DAEMON_NAME is stopped"
 fi
}

case "$1" in
  start)
    start
   ;;
  stop)
    stop
   ;;
  restart)
    stop
    start
   ;;
  status)
    status
   ;;
  *)
   echo "Scan [start|stop|status]"
esac
