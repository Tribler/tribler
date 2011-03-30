#!/usr/bin/env python

#
#  Synchronized publisher
#
#import zmq

from sys import argv, exit
from time import sleep
from threading import Semaphore, Lock
from getpass import getuser
from hashlib import md5

#  We wait for 10 subscribers

# config line format
# PEER_ID IP PORT KEY1 KEY2


configs = {}
clients = {}
config_lock = Lock()
got_configs = Semaphore(0)
subscribers = 0
client_count = 0


from twisted.internet.protocol import Factory
from twisted.protocols.basic import LineReceiver

from twisted.internet import epollreactor
epollreactor.install()
from twisted.internet import reactor


class ConfigProtocol(LineReceiver):
    def send_full_config(self):
        global subscribers, configs
        full_config = ""
        subscribers -= 1 # adjust subscriber count
        for i in range(len(clients)):
            full_config = full_config + " ".join(configs[i+1]) + "\r\n"
        for id,transport in clients.items():
            print "* Sending simulation configuration file to #%d..." %(id)
            transport.write(full_config)
            transport.write("END\r\n")

    def lineReceived(self, line):
        global config_lock, configs, subscribers
        if len(line)>2 and line[0:2] == "IP":
            config_lock.acquire()
            subscribers += 1
            subscriber_ip = line[3:]
            configs[subscribers][1] = subscriber_ip
            clients[subscribers] = self.transport
            config_line = " ".join(configs[subscribers])
            self.transport.write(config_line+"\r\n")
            print "* Peer #%d (%s)" %(subscribers, subscriber_ip)
            if subscribers == len(configs):
                self.send_full_config()
            config_lock.release()
        #if len(line)>4 and line[0:4] == "FULL":
        #    config_lock.acquire()
        #    if len(configs) == subscribers:
        #        self.transport.
        #    config_lock.release()

    def connectionLost(self, reason):
        global subscribers, config_lock
        config_lock.acquire()
        subscribers -= 1
        if subscribers == 0:
            reactor.stop()
        config_lock.release()


class ConfigFactory(Factory):
    protocol = ConfigProtocol

def main():
    global configs
    config_file = argv[1]
    for line in open(config_file,"r").readlines():
        if len(line) == 0: continue
        if line[0] == '#': continue
        parts = line.strip().split()
        configs[int(parts[0])] = parts # save all configurations idexed by peer ID
    expected_subscribers = len(configs)
    print "* Config server expecting %d peers..." %(expected_subscribers)

    md5sum = md5()
    md5sum.update(getuser())
    server_port = int(md5sum.hexdigest()[-16:], 16) % 20000 + 15000

    reactor.listenTCP(server_port, ConfigFactory())
    reactor.run()

if __name__ == '__main__':
    if len(argv) != 2:
        print "Usage: ./config_sync_server.py <peer-key-file>"
        exit(1)
    main()
