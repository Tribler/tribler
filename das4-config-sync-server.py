#!/usr/bin/env python

#
#  Synchronized publisher
#
from sys import argv, exit
from time import sleep, time
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
                
            print "*** Sending peers ip/port to peers:"
            for i, configtuple in enumerate(subscribers):
                print i+1,
                transport = configtuple[0]
                transport.write(full_config)
                transport.write("END\r\n")
            print " ***"
                
        print "*** Stopping reactor in 10 seconds ***"
        reactor.callLater(10, reactor.stop)

    def lineReceived(self, line):
        global configlock, subscribers, start_timestamp, initial_peer_delay
        
        if len(line) > 4 and line.startswith("TIME"):
            config_lock.acquire()
            
            nr_subscribers = len(subscribers) + 1

            if nr_subscribers == 1:
                start_timestamp = int(time()) + initial_peer_delay
            
            peer_time = float(line[5:])
            peer_time_diff = time() - peer_time
            
            address = self.transport.getPeer() 
            subscriber_ip = address.host 
            
            port = 12000 + nr_subscribers
            config_line = "%d %s %d %d"%(nr_subscribers, subscriber_ip, port, start_timestamp - peer_time_diff)
            self.transport.write(config_line + "\r\n")
            
            print "* Peer #%d (%s:%d) timediff: %.2f" %(nr_subscribers, subscriber_ip, port, peer_time_diff)
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
    if len(argv) > 3:
        server_port = int(argv[3])
    else:
        md5sum = md5()
        md5sum.update(getuser())
        server_port = int(md5sum.hexdigest()[-16:], 16) % 20000 + 15000
        
    print "* Config server expecting %d peers... on port %d" %(expected_subscribers, server_port)
    reactor.listenTCP(server_port, ConfigFactory())
    reactor.run()

if __name__ == '__main__':
    if len(argv) < 3:
        print "Usage: ./config_sync_server.py <peer-count> <initial_peer_delay>"
        exit(1)
    main()
