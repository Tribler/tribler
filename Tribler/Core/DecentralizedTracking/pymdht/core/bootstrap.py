# Copyright (C) 2011 Raul Jimenez
# Released under GNU LGPL 2.1
# See LICENSE.txt for more information
"""
Bootstrap node into the overlay by sending messages to:
- saved nodes (pymdht.state)
If the file exists, all nodes will be pinged (with a find_node message).
Those nodes that reply will be put in the routing table
- main and backup bootstrap nodes
These nodes are hardcoded (see core/bootstrap.main and core/bootstrap.backup)
Main nodes are run by us, backup nodes are wild nodes we have seen running for
a long time.
Each bootstrap step, a number of main nodes and backup nodes (see
*_NODES_PER_BOOTSTRAP) are used to peroform a lookup.
These bootstrap nodes SHOULD NOT be added to the routing table to avoid
overloading them (use is_bootstrap_node() before adding nodes to routing table!
"""

import os
import sys
import random
import logging

import ptime as time
import identifier
import message
import node

logger = logging.getLogger('dht')


BOOTSTRAP_MAIN_FILENAME = 'bootstrap.main'
BOOTSTRAP_BACKUP_FILENAME = 'bootstrap.backup'

MIN_RNODES_BOOTSTRAP = 10

SAVED_NODES_PER_BOOTSTRAP = 10
MAIN_NODES_PER_BOOTSTRAP = 1
BACKUP_NODES_PER_BOOTSTRAP = 7

SAVED_DELAY = .1
BOOTSTRAP_DELAY = 5

class OverlayBootstrapper(object):

    def __init__(self, my_id, saved_bootstrap_nodes, msg_f):
        self.my_id = my_id
        self.saved_bootstrap_nodes = saved_bootstrap_nodes
        self.msg_f = msg_f
        (self.main_bootstrap_nodes,
         self.backup_bootstrap_nodes) = _get_bootstrap_nodes()
        self.bootstrap_ips = set() #ips of nodes we used to bootstrap.
        # They shouldn't be added to routing table to avoid overload
        # (if possible)

    def do_bootstrap(self, num_rnodes):
        '''
        If there are saved nodes, all of them are pinged so we recover our
        saved routing table as best as we can.
        If there are no saved nodes (or not enough of them replied) we start
        performing maintenance lookup with main bootstrap nodes (and backup)
        until we have got enough nodes in the routing table.
        '''
        queries_to_send = []
        maintenance_lookup = None

        if self.saved_bootstrap_nodes:
            nodes = self.saved_bootstrap_nodes[:SAVED_NODES_PER_BOOTSTRAP]
            del self.saved_bootstrap_nodes[:SAVED_NODES_PER_BOOTSTRAP]
            queries_to_send = [self._get_bootstrap_query(node_) for node_ in nodes]
            delay = SAVED_DELAY
#            print '>> using saved nodes', len(nodes)
        elif num_rnodes > MIN_RNODES_BOOTSTRAP:
            delay = 0 # bootstrap done
        else:
            nodes = self._pop_bootstrap_nodes()
            maintenance_lookup = (self.my_id, nodes)
            delay = BOOTSTRAP_DELAY
#            print '>> using bootstrap nodes', len(nodes)
        return queries_to_send, maintenance_lookup, delay

    def bootstrap_done(self):
        #clean up stuff that will never be used
        self.saved_bootstrap_nodes = []
        self.main_bootstrap_nodes = []
        self.backup_bootstrap_nodes = []

    def is_bootstrap_node(self, node_):
        return node_.ip in self.bootstrap_ips

    def _get_bootstrap_query(self, node_):
        return self.msg_f.outgoing_find_node_query(node_, self.my_id, None)

    def _pop_bootstrap_nodes(self):
        nodes = []
        for _ in xrange(MAIN_NODES_PER_BOOTSTRAP):
            if self.main_bootstrap_nodes:
                i = random.randint(0, len(self.main_bootstrap_nodes) - 1)
                nodes.append(self.main_bootstrap_nodes.pop(i))
        for _ in xrange(BACKUP_NODES_PER_BOOTSTRAP):
            if self.backup_bootstrap_nodes:
                i = random.randint(0, len(self.backup_bootstrap_nodes) - 1)
                nodes.append(self.backup_bootstrap_nodes.pop(i))
        for node_ in nodes:
            self.bootstrap_ips.add(node_.ip)
        return nodes


def _sanitize_bootstrap_node(line):
    # no need to catch exceptions, get_bootstrap_nodes takes care of them
    ip, port_str = line.split()
    addr = ip, int(port_str)
    return node.Node(addr, version=None)

def _get_bootstrap_nodes():
    data_path = os.path.dirname(message.__file__)
    mainfile = os.path.join(data_path, BOOTSTRAP_MAIN_FILENAME)
    backfile = os.path.join(data_path, BOOTSTRAP_BACKUP_FILENAME)

    # Arno, 2012-05-25: py2exe support
    if hasattr(sys, "frozen"):
        print >>sys.stderr,"pymdht: bootstrap: Frozen mode"
        installdir = os.path.dirname(unicode(sys.executable,sys.getfilesystemencoding()))
        if sys.platform == "darwin":
            installdir = installdir.replace("MacOS","Resources")
        mainfile = os.path.join(installdir,"Tribler","Core","DecentralizedTracking","pymdht","core","bootstrap.main")
        backfile = os.path.join(installdir,"Tribler","Core","DecentralizedTracking","pymdht","core","bootstrap.backup")
    print >>sys.stderr,"pymdht: bootstrap: mainfile",mainfile
    print >>sys.stderr,"pymdht: bootstrap: backfile",backfile
    try:
        f = open(mainfile)
        main = [_sanitize_bootstrap_node(n) for n in f]
    except (Exception):
        logger.exception('main bootstrap file corrupted!')
        main = []
        raise
#    print 'main: %d nodes' % len(main)
    try:
        f = open(backfile)
        backup = [_sanitize_bootstrap_node(n) for n in f]
    except (Exception):
        logger.exception('backup bootstrap file corrupted!')
        backup = []
        raise
#    print 'backup: %d nodes' % len(backup)
    return main, backup
