# docker-haproxy-statsd

Small docker image (Alpine linux) that connects to HAProxy stats (HAProxy must be runing with stats), get stats in csv format, parse that file with rows you need and then send them via UDP to statsd server. 

Configuration is in ha-stats.conf file (connection parametars for HAProxy and Statsd). After changing config, rebuilding image is required. (or you can add volume and place template directory there)

More info is in ha-stats.py file on header section.
