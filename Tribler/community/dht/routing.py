import time
import random
import binascii

from threading import RLock
from socket import inet_aton

import datrie

from Tribler.pyipv8.ipv8.peer import Peer

NODE_STATUS_GOOD = 2
NODE_STATUS_UNKNOWN = 1
NODE_STATUS_BAD = 0

MAX_BUCKET_SIZE = 20


def id_to_binary_string(node_id):
    return format(int(node_id.encode('hex'), 16), '0160b')


def distance(a, b):
    return int(a.encode('hex'), 16) ^ int(b.encode('hex'), 16)


def calc_node_id(ip, mid):
    ip_bin = inet_aton(ip)
    ip_mask = '\x03\x0f\x3f\0xff'
    ip_masked = ''.join([chr(ord(ip_bin[i]) & ord(ip_mask[i])) for i in range(4)])

    crc32_unsigned = binascii.crc32(ip_masked) % (2 ** 32)
    crc32_bin = ('%08x' % crc32_unsigned).decode('hex')

    return crc32_bin[:3] + mid[:17]


class Node(Peer):
    """
    The Node class represents a peer within the DHT community
    """

    def __init__(self, *args, **kwargs):
        super(Node, self).__init__(*args, **kwargs)
        self.bucket = None
        self.last_response = 0
        self.last_query = 0
        self.failed = 0
        self.rtt = 0

    @property
    def id(self):
        return calc_node_id(self.address[0], self.mid)

    @property
    def last_contact(self):
        return max(self.last_response, self.last_query)

    @property
    def status(self):
        # A good node is a node has responded to one of our queries within the last 15 minutes, or has ever responded
        # to one of our queries and has sent us a query within the last 15 minutes. This is the same logic as
        # used in BEP-5
        now = time.time()
        if ((now - self.last_response) < 15 * 60) or (self.last_response > 0 and (now - self.last_query) < 15 * 60):
            return NODE_STATUS_GOOD
        elif self.failed >= 2:
            return NODE_STATUS_BAD
        return NODE_STATUS_UNKNOWN

    def distance(self, other_node):
        return distance(self.id, other_node.id)


class Bucket(object):
    """
    The Bucket class stores nodes that share common prefix ID.
    """

    def __init__(self, prefix_id, max_size=MAX_BUCKET_SIZE):
        self.nodes = {}
        self.prefix_id = prefix_id
        self.max_size = max_size
        self.last_changed = 0

    def generate_id(self):
        rand_node_id_bin = format(random.randint(0, 2 ** (160 - len(self.prefix_id))), '0160b')
        return format(int(rand_node_id_bin, 2), '040X').decode('hex')

    def owns(self, node_id):
        node_id_binary = id_to_binary_string(node_id)
        return node_id_binary.startswith(self.prefix_id)

    def get(self, node_id):
        return self.nodes.get(node_id)

    def add(self, node):
        # Is this node allowed to be in this bucket?
        if not self.owns(node.id):
            return False

        # Update existing node
        elif node.id in self.nodes:
            curr_node = self.nodes[node.id]
            curr_node.address = node.address
            self.last_changed = time.time()
            return True

        # Make room if needed
        if len(self.nodes) >= self.max_size:
            for n in self.nodes.itervalues():
                if n.status == NODE_STATUS_BAD:
                    del self.nodes[n.id]
                    break

            for n in self.nodes.itervalues():
                if node.rtt and n.rtt / node.rtt >= 2.0:
                    del self.nodes[n.id]
                    break

        # Insert
        if len(self.nodes) < self.max_size:
            self.nodes[node.id] = node
            node.bucket = self
            self.last_changed = time.time()
            return True

        return False

    def split(self):
        if len(self.nodes) < self.max_size:
            return False

        b_0 = Bucket(self.prefix_id + u'0', self.max_size)
        b_1 = Bucket(self.prefix_id + u'1', self.max_size)
        for node in self.nodes.itervalues():
            if b_0.owns(node.id):
                b_0.add(node)
            elif b_1.owns(node.id):
                b_1.add(node)
            else:
                self.logger.error('Failed to place node into bucket while splitting')
        return b_0, b_1


class RoutingTable(object):
    """
    The RoutingTable is a binary tree that keeps track of Nodes that we have a connection to.
    """

    def __init__(self, my_node_id):
        self.my_node_id = my_node_id
        self.trie = datrie.Trie(u'01')
        self.trie[u''] = Bucket(u'')
        self.lock = RLock()

    def get_bucket(self, node_id):
        node_id_binary = id_to_binary_string(node_id)
        return self.trie.longest_prefix_value(unicode(node_id_binary), default=None) or self.trie[u'']

    def add(self, node):
        with self.lock:
            bucket = self.get_bucket(node.id)
            node = bucket.get(node.id) or node

            # Add/update node
            if not bucket.add(node):
                # If adding the node failed, split the bucket
                # Splitting is only allowed if our own node_id falls within this bucket
                if bucket.owns(self.my_node_id):
                    bucket_0, bucket_1 = bucket.split()
                    self.trie[bucket.prefix_id + u'0'] = bucket_0
                    self.trie[bucket.prefix_id + u'1'] = bucket_1
                    del self.trie[bucket.prefix_id]

                    # Retry
                    return self.add(node)
            else:
                return node

    def has(self, node):
        return bool(self.get_bucket(node.id).get(node.id))

    def closest_nodes(self, node_id, max_nodes=8, exclude=None):
        with self.lock:
            hash_binary = unicode(id_to_binary_string(node_id))
            prefix = self.trie.longest_prefix(hash_binary, default=u'')

            nodes = set()
            for i in reversed(range(len(prefix) + 1)):
                for suffix in self.trie.suffixes(prefix[:i]):
                    bucket = self.trie[prefix[:i] + suffix]
                    nodes |= {node for node in bucket.nodes.itervalues() if node.status != NODE_STATUS_BAD and \
                                                                            (not exclude or node.id != exclude.id)}

                # Limit number of nodes returned
                if len(nodes) > max_nodes:
                    break

            # Ensure nodes are sorted by distance
            return sorted(nodes, key=lambda n: (distance(n.id, node_id), n.status))[:max_nodes]
