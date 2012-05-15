#!/usr/bin/env python

from time import mktime
import re
from os.path import isdir
from os import listdir, makedirs
from sys import argv, exit
from random import randint
from Tribler.dispersy.crypto import ec_generate_key, ec_to_public_bin, ec_to_private_bin

#def get_nodes():
#    for node in glob("peers/*"):
#        if node.startswith("peers/peer-"):
#            yield node

#def get_title(node):
#    if node.startswith("peers/peer-"):
#        return node[11:]
#    elif node == "peers/tracker":
#        return "tracker"
#    return "???"

def get_nodes(peer_dir):
    pattern = re.compile('[0-9]{5}')
    for d in listdir(peer_dir):
        if pattern.match(d):
            td = peer_dir + "/" + d
            if not isdir(td + "/data"): makedirs(td + "/data")
            yield td

def get_title(node):
    if re.match(".*[0-9]{5}", node):
        return node[-5:]
    elif len(node)>7 and node[-7:] == "tracker":
        return "tracker"
    return "???"

def generate(peer_path, records_per_time_unit, pause = 0, time_units = 5000, start_time = 1):
    ah = open(peer_path+"/data/availability.log", "w").close()
    bh = open(peer_path + "/data/bartercast.log", "w")
    time = start_time
    other_peer = 10
    upload = 20
    download = 10
    while time <= time_units:
        for i in range(records_per_time_unit):
            bh.write("%d %d %d %d\n" %(time, other_peer, time*upload+i, time*download+i))
        time = time + 1 + pause
    bh.close()


def generate_all(peers_directory, peer_count, records_per_time_unit, pause = 0, time_units = 5000, start_time = 1):
    time = start_time
    upload = 20
    download = 10
    while time <= time_units:
        for i in range(records_per_time_unit):
            p1 = randint(1,peer_count)
            p2 = p1
            while p2 == p1:
                p2 = randint(1, peer_count)
            p1_path=peers_directory+"/%05d/data/bartercast.log" %(p1)
            p1_h = open(p1_path, "a")
            p1_h.write("%d %d %d %d\n" %(time, p2, time*upload+i, time*download+i))
            p1_h.close()
        time = time + 1 + pause

def setup_peer_dir(peers_directory, peer_count):
    for i in range(peer_count):
        td = peers_directory+"/"+"%05d" %(i+1)
        if not isdir(td): makedirs(td)
    with open(peers_directory + "/peer.count", "w") as f:
        f.write("%d\n" %(peer_count))
    with open(peers_directory + "/peer-keys", 'w') as f:
        for i in range(peer_count):
            rsa = ec_generate_key(u"low")
            f.write("%(id)s %(ip)s %(port)d %(public_key)s %(private_key)s\n" % \
                          {'id': i+1, #'peer-%05d' % i,
                           'ip': '0.0.0.0',
                           'port': 12000 + i,
                           'public_key': ec_to_public_bin(rsa).encode("HEX"),
                           'private_key': ec_to_private_bin(rsa).encode("HEX")
                           }
                          )
    for node in get_nodes(peers_directory):
        open(node+"/data/bartercast.log", "w").close()
        open(node+"/data/availability.log", "w").close()

if __name__ == "__main__":
    if len(argv) != 3:
        print "Usage: %s <new-peers-directory> <peer-count>" %(argv[0])
        exit(1)
    peers_directory = argv[1]
    peer_count = int(argv[2])
    setup_peer_dir(peers_directory, peer_count)
    generate(peers_directory+"/00001", 25, time_units=1)
    #generate(peers_directory+"/00002", 10)
    #generate_all(peers_directory, peer_count, 25, time_units = 25)

