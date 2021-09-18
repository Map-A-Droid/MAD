#Moving towards scalability...

1) Ensure Python >= 3.8 venv is present
2) `source venv/bin/activate`
3) `pip3 install -r requirements.txt`
4) `cp alembic.ini.example alembic.ini`
5) Adjust `sqlalchemy.url` to yield DB connection data: `mysql+aiomysql://db_user:password@host:port/db_name`
6) `alembic upgrade head`

###Modes of operation:
  - Single Host (small setups, approx <20)
    > Use start.py like you normally would after having installed requirements.txt
  - Single MAD core + MitmMapper in a single process (1 core, small to mediocre setups), multiple MitmReceiver hosts/processes anywhere
    - Use start.py like normally
    - Start additional MitmReceivers using start_mitmreceiver.py
    - Check config parameters as to how to connect additiona MitmReceivers using gRPC to the main MAD instance (namely mappingmanager_ip and mitmmapper_ip need to point to main MAD host)
    - Adjust LoadBalancer behaviour (or Reverse Proxy) accordingly.
      1) Set MitmReceiver's unix sockets per process using mitm_unix_socket with full paths to the socket files
      2) Point ReverseProxy/LoadBalancer to those accordingly
      Sample NGINX + Supervisord:
      NGINX config:
      ```
      upstream mad_mitm_receiver {
        server unix:/tmp/mad_mitm_receiver_1.sock fail_timeout=0 max_conns=100 max_fails=0;
        server unix:/tmp/mad_mitm_receiver_2.sock fail_timeout=0 max_conns=100 max_fails=0;
      }

      server {
            listen 80 default_server;
            listen [::]:80 default_server;
            root /var/www/html;

            # Add index.php to the list if you are using PHP
            index index.html index.htm index.nginx-debian.html;

            server_name _;

            location / {
                    proxy_set_header Host $http_host;
                    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
                    proxy_redirect off;
                    proxy_buffering off;
                    proxy_pass http://mad_mitm_receiver;
            }

      }
      ```
      Supervisord config:
      ```
      [program:mad_mitm_receiver]
      numprocs = 2
      numprocs_start = 1
      process_name = mad_mitm_receiver_%(process_num)s
      command=/opt/MAD/venv/bin/python3 /opt/MAD/start_mitmreceiver.py -os -vv -ec --mitm_unix_socket=/tmp/mad_mitm_receiver_%(process_num)s.sock
      environment=PATH="/opt/MAD/venv/bin:%(ENV_PATH)s"
      user = www-data
      directory=/opt/MAD
      #directory=/opt/map_all/MADDev
      startsec=15
      startretries=3
      autorestart=true
      stopsignal=INT
      stopwaitsecs=60
      stdout_logfile=/var/log/mad_mitm_receiver.log
      redirect_stderr = true
      ```
  - MAD Core, MitmMapper running on same host (or each on their own) + multiple MitmReceivers as shown above
    - Use start_core.py, start_mitmmapper.py, start_mitmreceiver.py accordingly
    - Adjust mappingmanager_ip and mitmmapper_ip in the configs

Please provide feedback on runtype and performance, especially amount of devices being run in a single MAD core instance :)

Keep in mind that all of MAD is now based on asyncio. Meaning a single .py script being executed runs all code in a single core.

Thus MitmReceiver may show high CPU usage (on a single core). A lot of time is spent waiting for DB processing as well.

Also, the default db_poolsize of 2 may be too little in some situations, do play around with that parameter.

### Potential performance improvement:
`pip3 install uvloop`

### TODO:
- Consider splitting up more components, i.e. MappingManager to be extended to gRPC entirely
- Split RouteManagers to components
- Thus connect multiple WebsocketServers to scale by device/worker count