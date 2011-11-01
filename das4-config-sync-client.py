#!/usr/bin/env python
#
from sys import argv, exit
from os import getpid
from getpass import getuser
from hashlib import md5

from twisted.internet.protocol import ClientFactory
from twisted.protocols.basic import LineReceiver
from twisted.internet import reactor


class ConfigClientProtocol(LineReceiver):
    def connectionMade(self):
        print my_ip
        my_ip = argv[2]
        self.sendLine("IP "+my_ip)

    def lineReceived(self, data):
        print data
        username = getuser()
        parts = data.strip().split('#')
        starting_timestamp = int(parts[0])
        config_line = parts[1]
        self.my_id = int(config_line.split()[0])
        my_id_str = "%05d" %(self.my_id) 
        f = open("/tmp/%s/dispersy/peer_%s.conf" %(username, my_id_str), "w")
        f.write(data)
        f.close()
        print my_id_str, starting_timestamp

class ConfigClientFactory(ClientFactory):
    def buildProtocol(self, addr):
        return ConfigClientProtocol()

def main():
    sync_server = argv[1]

    # determine port based on the process owner's username
    md5sum = md5()
    md5sum.update(getuser())
    server_port = int(md5sum.hexdigest()[-16:], 16) % 20000 + 15000

    reactor.connectTCP(sync_server, server_port, ConfigClientFactory())
    reactor.run()

if __name__ == '__main__':
    if len(argv) != 3:
        print "Usage: ./config_sync_client.py <sync_server> <my_ip>"
        exit(1)
    main()