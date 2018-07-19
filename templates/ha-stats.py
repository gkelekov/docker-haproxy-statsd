#!/usr/bin/python
'''
Get HAProxy stats, parse and push to statsd server

Usage: python ha-stats.py [-h] [-f] [-t]
Optional arguments:
  -h, --help            Prints this line
  -f, --config_file     Config file location (if not with default name "ha-stats.conf", and not in same directory as "ha-stats.py")
                        
  -t, --test            Execute once and terminate. For testing configuration.

This script extractes only fields that are marked with "*". If you need more add them to in list for report (line 103)

Queue
* qcur - current queued requests
* qmax - max value of qcur (queued requests)

Session rate
* rate - number of sessions per second over last elapsed second
  rate_lim - configured limit on new sessions per second
* rate_max - max number of new sessions per second

Session
* scur - current sessions
* smax - max sessions
  slim - configured session limit
* hrsp_1xx - http responses with 1xx code
* hrsp_2xx - http responses with 2xx code
* hrsp_3xx - http responses with 3xx code
* hrsp_4xx - http responses with 4xx code
* hrsp_5xx - http responses with 5xx code
  hrsp_other - http responses with other codes (protocol error)
  qtime - the average queue time in ms over the 1024 last requests
  ctime - the average connect time in ms over the 1024 last requests
  rtime - the average response time in ms over the 1024 last requests
  ttime - the average total session time in ms over the 1024 last requests
  lbtot - total number of times a server was selected, either for new sessions, or when re-dispatching

Bytes
* bin - bytes in
* bout - bytes out

Denied
  dreq - requests denied because of security concerns
  dresp - responses denied because of security concerns
 
Errors
  ereq - request errors. Early termination from the client, before the request has been sent, read error from the client, client timeout, client closed connection, various bad requests from the client.
  econ - number of requests that encountered an error trying to connect to a backend server. 
  eresp - response errors. Some other errors are: write error on the client socket, failure applying filters to the response.
     
Warnings
  wretr - number of times a connection to a server was retried.
  wredis - number of times a request was redispatched to another server. 

Server
  status - status (UP/DOWN/NOLB/MAINT/MAINT(via)...)
  weight - total weight (backend), server weight (server)
  act - number of active servers (backend), server is active (server)


More documentation info:
http://cbonte.github.io/haproxy-dconv/configuration-1.5.html#9.1
'''

import argparse
import ConfigParser
import csv
import os
import requests
import sys
import socket
import time
#from requests.auth import HTTPBasicAuth



# Connect to haproxy stats, authenticate and get stats in csv format
def get_ha_stats(url, user=None, password=None):
    auth = None
    if user:
        auth = requests.auth.HTTPBasicAuth(user, password)
    i = requests.get(url, auth=auth)
    i.raise_for_status()
    data = i.content.lstrip('# ')
    return csv.DictReader(data.splitlines())


# Sort haproxy stats, filter it, and send to statd via simple UDP socket
def push_to_statsd(rows,
                     host=os.getenv('STATSD_HOST', ''),
                     port=os.getenv('STATSD_PORT', ),
                     namespace=os.getenv('STATSD_NAMESPACE', 'haproxy')):
    udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    stat_count = 0

    # Report for each row
    for row in rows:
        name = '.'.join([namespace, row['pxname'], row['svname']])
        # Mostly used config:
        # for stat in ['qcur','qmax','rate','rate_max','scur','smax','hrsp_1xx','hrsp_2xx','hrsp_3xx','hrsp_4xx','hrsp_5xx','qtime','ctime','rtime','ttime','bin','bout','dreq','dresp','ereq','econ','eresp']:
        # Default config:
        for data in ['qcur','qmax','scur','smax', 'rate','rate_max', 'hrsp_1xx','hrsp_2xx','hrsp_3xx','hrsp_4xx','hrsp_5xx','bin','bout']:
            value = row.get(data) or 0
            udp.sendto(
                '%s.%s:%s|g' % (name, data, value), (host, port))
            # Add sleep of 10 ms so that all UDP's have time to be processed on statsd - can be removed on production setup
            # time.sleep (10.0 / 1000.0)
            stat_count += 1
    return stat_count

# Main run, while true if no error occures or
if __name__ == '__main__':
    parse = argparse.ArgumentParser(
        description='Get haproxy stats, parse needed stats, and push it to statsd')
    parse.add_argument('-f',  '--config_file',
                        help='Location and name of configuration file, if not bundled with ha-stats.py',
                        default='./ha-stats.conf')
    parse.add_argument('-t', '--test',
                        action='store_true',
                        help='Execute once and terminate. For testing configuration.',
                        default=False)

    args = parse.parse_args()
    conf = ConfigParser.ConfigParser({
        'ha_url': os.getenv('HAPROXY_HOST', 'http://127.0.0.1:80/;csv'),
        'ha_user': os.getenv('HAPROXY_USER',''),
        'ha_pass': os.getenv('HAPROXY_PASS',''),
        'statsd_namespace': os.getenv('STATSD_NAMESPACE', 'haproxy.stats'),
        'statsd_host': os.getenv('STATSD_HOST', '127.0.0.1'),
        'statsd_port': os.getenv('STATSD_PORT', 8125),
        'sleep': '10',
    })
    conf.add_section('ha-stats')
    conf.read(args.config_file)

    # Get sleep/interval/period time from config file
    sleep = conf.getfloat('ha-stats', 'sleep')

    # Add namespace for statsd - get local hostname
    namespace = conf.get('ha-stats', 'statsd_namespace')
    if '(HOSTNAME)' in namespace:
        namespace = namespace.replace('(HOSTNAME)', socket.gethostname())
    
    try:
        while True:
            get_stats = get_ha_stats(
                conf.get('ha-stats', 'ha_url'),
                user=conf.get('ha-stats', 'ha_user'),
                password=conf.get('ha-stats', 'ha_pass'))

            push_statsd = push_to_statsd(
                get_stats,
                namespace=namespace,
                host=conf.get('ha-stats', 'statsd_host'),
                port=conf.getint('ha-stats', 'statsd_port'))

            print(time.strftime("%Y-%m-%d %H:%M:%S") + (" - Reported %s stats" % push_statsd))
            if args.test:
                exit(0)
            else:
                time.sleep(sleep)
    except KeyboardInterrupt:
        exit(0)