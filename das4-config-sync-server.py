#!/usr/bin/env python

#
#  Synchronized publisher
#
from sys import argv, exit
from time import sleep
from threading import Semaphore, Lock
from getpass import getuser
from hashlib import md5

start_timestamp = 0
initial_peer_delay = 0
expected_subscribers = 0
subscribers = 0

config_lock = Lock()

from twisted.internet.protocol import Factory
from twisted.protocols.basic import LineReceiver

from twisted.internet import epollreactor
epollreactor.install()
from twisted.internet import reactor

class ConfigProtocol(LineReceiver):

    def lineReceived(self, line):
        global configlock, subscribers, start_timestamp, initial_peer_delay
        
        if len(line)>2 and line[0:2] == "IP":
            config_lock.acquire()
            
            subscribers += 1
            if subscribers == 1:
                from time import time
                start_timestamp = int(time()) + initial_peer_delay
                
            subscriber_ip = line[3:]
            
            port = 12000 + subscribers
            config_line = str(start_timestamp) + "#%d %s:%d"%(subscribers, subscriber_ip, port)
            self.transport.write(config_line + "\r\n")
            print "* Peer #%d (%s:%d)" %(subscribers, subscriber_ip, port)

            config_lock.release()
            if subscribers == expected_subscribers:
                print "*** Stopping reactor ***"
                reactor.stop()
                
class ConfigFactory(Factory):
    protocol = ConfigProtocol

def main():
    global start_timestamp, expected_subscribers, initial_peer_delay
    expected_subscribers = int(argv[1])
    initial_peer_delay = int(argv[2])
    print "* Config server expecting %d peers..." %(expected_subscribers)

    md5sum = md5()
    md5sum.update(getuser())
    server_port = int(md5sum.hexdigest()[-16:], 16) % 20000 + 15000

    reactor.listenTCP(server_port, ConfigFactory())
    reactor.run()

if __name__ == '__main__':
    if len(argv) != 3:
        print "Usage: ./config_sync_server.py <peer-count> <initial_peer_delay>"
        exit(1)
    main()
