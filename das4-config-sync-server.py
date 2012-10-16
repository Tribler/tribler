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
subscribers = []

config_lock = Lock()

from twisted.internet.protocol import Factory
from twisted.protocols.basic import LineReceiver

from twisted.internet import epollreactor
epollreactor.install()
from twisted.internet import reactor

class ConfigProtocol(LineReceiver):

    def send_full_config(self):
        global configlock, subscribers
        with config_lock:
            full_config = ""
            for transport, ip, port in subscribers:
                full_config += "%s %d\r\n"%(ip, port)
                
            for i, configtuple in enumerate(subscribers):
                print "*** Sending peers ip/port to peer %d ***"%(i+1)
                transport = configtuple[0]
                transport.write(full_config)
                transport.write("END\r\n")
                
        print "*** Stopping reactor in 10 seconds ***"
        reactor.callLater(10, reactor.stop)

    def lineReceived(self, line):
        global configlock, subscribers, start_timestamp, initial_peer_delay
        
        if len(line)>2 and line[0:2] == "IP":
            config_lock.acquire()
            
            if subscribers == 1:
                from time import time
                start_timestamp = int(time()) + initial_peer_delay
                
            nr_subscribers = len(subscribers) + 1
            subscriber_ip2 = line[3:]
            
            address = self.transport.getPeer() 
            subscriber_ip = address.host 
            
            port = 12000 + nr_subscribers
            config_line = "%d %s %d"%(nr_subscribers, subscriber_ip, port)
            self.transport.write(config_line + "\r\n")
            
            print "* Peer #%d (%s %s:%d)" %(nr_subscribers, subscriber_ip, subscriber_ip2, port)
            subscribers.append((self.transport, subscriber_ip, port))

            config_lock.release()
            if nr_subscribers == expected_subscribers:
                self.send_full_config()
                
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
