# Copyright (C) 2009-2011 Raul Jimenez
# Released under GNU LGPL 2.1
# See LICENSE.txt for more information


"""
FORMAT
The first line contains this node's identifier

The rest of the lines contain routing table nodes
log_distance hex_id version ip port rtt(ms) uptime(s)

EXAMPLE
f33d5f1aa60c6298db205b967525d802a60f9902
137 f33d5c00b165dcf0358ed4fcaea05a54848f1a95 NS2323   99.192.23.157 38453 1088  43680
139 f33d563ce084daf4acbe909c48b649ac7a09e25a UT3434   109.237.98.97 24996   84  19376
139 f33d52fa381be82ca8ba00bb4e297ba2205fc4bc UT3434    46.55.30.252 12580   92   8982
139 f33d558dfadb8d80ed8ff7a6060ae9b7ab1fa930 UT3434  71.227.220.238 41988  233  19206
139 f33d57845353732838b4dabcfce37216ed56a8fa UT3434    66.122.12.68 45682  239  46375
"""

import sys
import logging

import ptime as time
from identifier import Id
from node import Node
from message import version_repr

logger = logging.getLogger('dht')


def save(my_id, rnodes, filename):
    f = open(filename, 'w')
    f.write('%r\n' % my_id)
    for rnode in rnodes:
        if rnode.rtt == 99:
            rtt = rnode.real_rtt
        else:
            rtt = rnode.rtt
        f.write('%d %r %8s %15s %5d %4d %6d\n' % (
                my_id.distance(rnode.id).log,
                rnode.id, version_repr(rnode.version),
                rnode.addr[0], rnode.addr[1],
                rtt * 1000,
                time.time() -rnode.creation_ts ))
    f.close()

def load(filename):
    my_id = None
    nodes = []
    try:
        f = open(filename)
        hex_id = f.readline().strip()
        my_id = Id(hex_id)
        for line in f:
            _, hex_id, _, ip, port, _, _ = line.split()
            addr = (ip, int(port))
            node_ = Node(addr, Id(hex_id))
            nodes.append(node_)
    except(IOError):
        logger.debug("No state saved, loading default.")
        return None, []
    except:
        logger.exception("Error when loading state, loading default.")
        #raise # debug only
        return None, []
    f.close
    return my_id, nodes
