"""
This is the server part of the node, where queries are parsed and responses
created.

"""
import logging
import logging_conf

import message
import tracker
import token_manager

logger = logging.getLogger('dht')

NUM_NODES = 8


class Responder(object):

    def __init__(self, my_id, routing_m, msg_f,
                 bootstrap_mode=False):
        self._my_id = my_id
        self._routing_m = routing_m
        self.msg_f = msg_f
        self.bootstrap_mode = bootstrap_mode
        self._tracker = tracker.Tracker()
        self._token_m = token_manager.TokenManager()

    def get_response(self, msg):
        if msg.query == message.PING:
            if self.bootstrap_mode:
                return
            return self.msg_f.outgoing_ping_response(msg.src_node)
        elif msg.query == message.FIND_NODE:
            log_distance = msg.target.distance(self._my_id).log
            rnodes = self._routing_m.get_closest_rnodes(log_distance,
                                                        NUM_NODES, False)
            # TODO: return the closest rnodes to the target instead of the 8
            # first in the bucket.
            return self.msg_f.outgoing_find_node_response(
                msg.src_node, rnodes)
        elif msg.query == message.GET_PEERS:
            token = self._token_m.get(msg.src_node.ip)
            log_distance = msg.info_hash.distance(self._my_id).log
            rnodes = self._routing_m.get_closest_rnodes(log_distance,
                                                        NUM_NODES, False)
            # TODO: return the closest rnodes to the target instead of the 8
            # first in the bucket.
            peers = self._tracker.get(msg.info_hash)
            if peers:
                logger.debug('RESPONDING with PEERS:\n%r' % peers)
            return self.msg_f.outgoing_get_peers_response(
                msg.src_node, token, nodes=rnodes, peers=peers)
        elif msg.query == message.ANNOUNCE_PEER:
            if msg.token and self._token_m.check(msg.src_node.ip, msg.token):
                peer_addr = (msg.src_addr[0], msg.bt_port)
                self._tracker.put(msg.info_hash, peer_addr)
                return self.msg_f.outgoing_announce_peer_response(msg.src_node)
            else:
                logger.warning('BAD TOKEN!')
                return
        else:
            logger.debug('Invalid QUERY: %r' % (msg.query))
            # TODO: maybe send an error back?
