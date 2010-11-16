# Copyright (C) 2009-2010 Flutra Osmani, Raul Jimenez
# Released under GNU LGPL 2.1
# See LICENSE.txt for more information

from nose.tools import eq_, ok_, assert_raises
import test_const as tc
import logging, logging_conf

import ptime as time

import querier
from querier import Query
from routing_manager_p3 import RoutingManagerMock
import lookup_manager_p3 as lookup_manager
import message
from identifier import Id, ID_SIZE_BYTES
from node import Node

logging_conf.testing_setup(__name__)
logger = logging.getLogger('dht')

#assert 0
class _TestLookupQueue:

    def setup(self):
        self.lookup = lookup_manager._LookupQueue(tc.INFO_HASH_ZERO, 4)

    def test_add_pop1(self):
        nodes = (tc.NODES_LD_IH[157][0],
                 tc.NODES_LD_IH[158][1],
                 tc.NODES_LD_IH[154][2],
                 tc.NODES_LD_IH[159][3],
                 tc.NODES_LD_IH[158][4],
                 tc.NODES_LD_IH[152][5],)
        self.lookup.add(nodes)
        # Just the 4 closest nodes are added
        #This second add doesn't affect (duplicates are ignored)
        self.lookup.add(nodes)
        eq_(self.lookup.pop_closest_node(), tc.NODES_LD_IH[152][5])
        eq_(self.lookup.pop_closest_node(), tc.NODES_LD_IH[154][2])
        eq_(self.lookup.pop_closest_node(), tc.NODES_LD_IH[157][0])
        eq_(self.lookup.pop_closest_node(), tc.NODES_LD_IH[158][1])
        # Now the queue is empty
        assert_raises(IndexError, self.lookup.pop_closest_node)
        self.lookup.add(nodes)
        # The nodes added are ingnored
        assert_raises(IndexError, self.lookup.pop_closest_node)


    def _test_add_pop2(self):
        self.lookup.add(tc.NODES[3:6])
        eq_(self.lookup.pop_closest_node(), tc.NODES[3])
        eq_(self.lookup.pop_closest_node(), tc.NODES[4])
        self.lookup.add(tc.NODES[2:3])
        eq_(self.lookup.pop_closest_node(), tc.NODES[2])
        eq_(self.lookup.pop_closest_node(), tc.NODES[5])
        # Empty
        assert_raises(IndexError, self.lookup.pop_closest_node)
        # This add only affects 0,1,6,7
        self.lookup.add(tc.NODES)
        eq_(self.lookup.pop_closest_node(), tc.NODES[0])
        eq_(self.lookup.pop_closest_node(), tc.NODES[1])
        eq_(self.lookup.pop_closest_node(), tc.NODES[6])
        eq_(self.lookup.pop_closest_node(), tc.NODES[7])


class TestGetPeersLookup:

    def _callback(self, peers):
        self.got_peers = peers

    def setup(self):
        self.got_peers = None
        self.bootstrap_nodes = [tc.NODES_LD_IH[159][0],
                                tc.NODES_LD_IH[158][1],
                                tc.CLIENT_NODE,
                                tc.NODES_LD_IH[157][3],
                                tc.NODES_LD_IH[155][4],]
        self.lookup = lookup_manager.GetPeersLookup(tc.CLIENT_ID,
                                                    tc.INFO_HASH_ZERO,
                                                    self._callback,
                                                    self.bootstrap_nodes)
        self.get_peers_msg = message.OutgoingGetPeersQuery(
            tc.CLIENT_ID, tc.INFO_HASH_ZERO)

        
    def test_complete(self):
        to_send = self.lookup.start()

        # The node won't query itself
        del self.bootstrap_nodes[2]
        
        expected = [Query(self.get_peers_msg, n) for n in self.bootstrap_nodes]
        for result, expected in zip(to_send, expected):
            eq_(result.msg, expected.msg)
            eq_(result.dstnode, expected.dstnode)
        eq_(self.lookup.num_parallel_queries, 4)

        # Node receives a response from a node
        node_ = tc.NODES_LD_IH[158][1]
        nodes = [tc.NODES_LD_IH[156][5]]
        msg = message.OutgoingGetPeersResponse(node_.id, 'token', nodes)
        msg = msg.encode('Z')
        msg = message.IncomingMsg(msg, node_.addr)
        #print 'nodes2', msg.nodes2
        result = self.lookup.on_response_received(msg, node_)
        expected = [Query(self.get_peers_msg, nodes[0])]
        eq_(result[0].msg, expected[0].msg)
        eq_(result[0].dstnode, expected[0].dstnode)
        eq_(self.lookup.num_parallel_queries, 4)
        # Timeout
        eq_(self.lookup.on_timeout(tc.NODES_LD_IH[159][0]), [])
        eq_(self.lookup.num_parallel_queries, 3)
            

        return

        """Start sends two parallel queries to the closest
        bootstrap nodes (to the INFO_HASH)

        """
        # Ongoing queries to (sorted: oldest first):
        # 155-4, 157-3, 
        # Queued nodes to query (sorted by log_distance to info_hash):
        # 158-1, 159-0
        # Notice 159-2 is kicked out from the queue
        logger.critical("")
        eq_(self.lookup.num_parallel_queries, 2)
        nodes = [tc.NODES_LD_IH[157][5],
                 tc.NODES_LD_IH[152][6],
                 tc.NODES_LD_IH[158][7]]
        self.lookup.on_response_received(*_gen_nodes_args(
                tc.NODES_LD_IH[157][3],
                nodes))
        eq_(self.lookup._get_announce_candidates(),
            [tc.NODES_LD_IH[157][3],
             ])
        # This response triggers a new query (to 152-6)
        eq_(self.lookup.num_parallel_queries, 2)
        # Ongoing queries to (sorted: oldest first):
        # 155-4, 152-6
        # Queued nodes to query (sorted by log_distance to info_hash):
        # 157-5, 158-1, 158-7, 159-0
        self.lookup.on_timeout(tc.NODES_LD_IH[155][4])
        eq_(self.lookup.num_parallel_queries, 2)
        # This timeout triggers a new query (to 157-5)
        eq_(self.lookup.num_parallel_queries, 2) 
        # Ongoing queries to (sorted: oldest first):
        # 155-4, 157-5 
        # Queued nodes to query (sorted by log_distance to info_hash):
        # 158-1, 158-7, 159-0
        self.lookup.on_timeout(tc.NODES_LD_IH[155][4])
        # This timeout triggers a new query (to 158-1)
        eq_(self.lookup.num_parallel_queries, 2) 
        # Ongoing queries to (sorted: oldest first):
        # 152-6, 158-1
        # Queued nodes to query (sorted by log_distance to info_hash):
        # 158-7, 159-0
        nodes = [tc.NODES_LD_IH[151][8],
                 tc.NODES_LD_IH[150][9]]
        self.lookup.on_response(*_gen_nodes_args(
                tc.NODES_LD_IH[152][6],
                nodes))
        eq_(self.lookup._get_announce_candidates(),
            [tc.NODES_LD_IH[152][6],
             tc.NODES_LD_IH[157][3],
             ])
        # This response triggers a new query (to 150-9)
        eq_(self.lookup.num_parallel_queries, 2) 
        # Ongoing queries to (sorted: oldest first):
        # 157-5, 150-9
        # Queued nodes to query (sorted by log_distance to info_hash):
        # 151-8, 158-7, 159-0
        nodes = [tc.NODES_LD_IH[151][10],
                 tc.NODES_LD_IH[151][11],
                 tc.NODES_LD_IH[156][12],
                 tc.NODES_LD_IH[156][13],
                 ]
        self.lookup.on_response_received(*_gen_nodes_args(
                tc.NODES_LD_IH[157][5],
                nodes))
        eq_(self.lookup._get_announce_candidates(),
            [tc.NODES_LD_IH[152][6],
             tc.NODES_LD_IH[157][3],
             tc.NODES_LD_IH[157][5],
                                               ])
        # This response triggers a new query (to 151-8)
        eq_(self.lookup.num_parallel_queries, 2) 
        # Ongoing queries to (sorted: oldest first):
        # 150-9, 151-8
        # Queued nodes to query (sorted by log_distance to info_hash):
        # 151-10, 151-11, 156-12, 156-13
        # Notice that the lookup queue size limit is 4, therefore
        # 158-7 and 159-0 are removed from the queue
        self.lookup.on_error_received(None, tc.NODES_LD_IH[151][8])
        # This error triggers a new query (to 151-8)
        eq_(self.lookup.num_parallel_queries, 2)
        # Ongoing queries to (sorted: oldest first):
        # 150-9, 151-10
        # Queued nodes to query (sorted by log_distance to info_hash):
        # 151-11, 156-12, 156-13
        self.lookup.on_timeout(tc.NODES_LD_IH[151][8])
        # This timeout triggers a new query (to 151-11)
        eq_(self.lookup.num_parallel_queries, 2)
        # Ongoing queries to (sorted: oldest first):
        # 151-10, 151-11
        # Queued nodes to query (sorted by log_distance to info_hash):
        # 156-12, 156-13
        nodes = [tc.NODES_LD_IH[144][14],
                 tc.NODES_LD_IH[145][15],
                 tc.NODES_LD_IH[145][16],
                 tc.NODES_LD_IH[145][17],
                 ]
        self.lookup.on_response_received(*_gen_nodes_args(
                tc.NODES_LD_IH[151][10],
                nodes))
        eq_(self.lookup._get_announce_candidates(), [tc.NODES_LD_IH[151][10],
                                                     tc.NODES_LD_IH[152][6],
                                                     tc.NODES_LD_IH[157][3],
                                               ])
        # This response triggers a new query (to 144-14)
        eq_(self.lookup.num_parallel_queries, 2)
        # Ongoing queries to (sorted: oldest first):
        # 151-11, 144-14
        # Queued nodes to query (sorted by log_distance to info_hash):
        # Notice 156-13 is removed
        # 145-15, 145-16, 145-17, 156-12
        peers = [tc.NO_ADDR]
        ok_(not self.got_peers)
        self.lookup.on_response_received(*_gen_peers_args(
                tc.NODES_LD_IH[144][14],
                peers))
        eq_(self.lookup._get_announce_candidates(), [tc.NODES_LD_IH[144][14],
                                               tc.NODES_LD_IH[151][10],
                                               tc.NODES_LD_IH[152][6],
                                               ])
        ok_(self.got_peers)
        self.got_peers = False
        # The response with peers halves parallelism to 1.
        # No new query is  triggered.
        eq_(self.lookup.num_parallel_queries, 1)
        # Ongoing queries to (sorted: oldest first):
        # 151-11
        # Queued nodes to query (sorted by log_distance to info_hash):
        # 145-15, 145-16, 156-12
        self.lookup.on_timeout(tc.NODES_LD_IH[151][11])
        # This timeout triggers a new query (to 145-15)
        eq_(self.lookup.num_parallel_queries, 1)
        # Ongoing queries to (sorted: oldest first):
        # 145-15
        # Queued nodes to query (sorted by log_distance to info_hash):
        # 145-16, 145-17, 156-12
        peers = [tc.NO_ADDR]
        ok_(not self.got_peers)
        self.lookup.on_response_received(*_gen_peers_args(
                tc.NODES_LD_IH[145][15],
                peers))
        # This response triggers a new query (to 145-16)
        # The parallelism is not halved (remains 1).
        eq_(self.lookup.num_parallel_queries, 1)
        # Ongoing queries to (sorted: oldest first):
        # 145-16
        # Queued nodes to query (sorted by log_distance to info_hash):
        # 145-17, 156-12
        eq_(self.lookup._get_announce_candidates(), [tc.NODES_LD_IH[144][14],
                                               tc.NODES_LD_IH[145][15],
                                               tc.NODES_LD_IH[151][10],
                                               ])
        ok_(self.got_peers)
        self.got_peers = False
        self.lookup.on_timeout(tc.NODES_LD_IH[145][16])
        # This timeout triggers a new query (to 145-17)
        eq_(self.lookup.num_parallel_queries, 1)
        # Ongoing queries to (sorted: oldest first):
        # 145-17
        # Queued nodes to query (sorted by log_distance to info_hash):
        # 156-12
        self.lookup.on_timeout(tc.NODES_LD_IH[145][17])
        # This timeout triggers a new query (to 156-12)
        return
        eq_(self.lookup.num_parallel_queries, 1)
        # Ongoing queries to (sorted: oldest first):
        # 156-12
        # Queued nodes to query (sorted by log_distance to info_hash):
        # 
        nodes = [tc.NODES_LD_IH[144][18],
                 tc.NODES_LD_IH[145][19],
                 ]
        self.lookup.on_response_received(*_gen_nodes_args(
                tc.NODES_LD_IH[156][12],
                nodes))
        eq_(self.lookup._get_announce_candidates(), [tc.NODES_LD_IH[144][14],
                                               tc.NODES_LD_IH[145][15],
                                               tc.NODES_LD_IH[151][10],
                                               ])
        # This response triggers a new query (to 144-18)
        eq_(self.lookup.num_parallel_queries, 1)
        # Ongoing queries to (sorted: oldest first):
        # 144-18
        # Queued nodes to query (sorted by log_distance to info_hash):
        # 145-19
        peers = [tc.NO_ADDR]
        ok_(not self.got_peers)
        self.lookup.on_response_received(*_gen_peers_args(
                tc.NODES_LD_IH[144][18],
                peers))
        eq_(self.lookup._get_announce_candidates(), [tc.NODES_LD_IH[144][14],
                                               tc.NODES_LD_IH[144][18],
                                               tc.NODES_LD_IH[145][15],
                                               ])
        ok_(self.got_peers)
        self.got_peers = False
        # This timeout triggers a new query (145-19)
        eq_(self.lookup.num_parallel_queries, 0)
        # Ongoing queries to (sorted: oldest first):
        # 145-19
        # Queued nodes to query (sorted by log_distance to info_hash):
        #
        ok_(not self.lookup.is_done)
        self.lookup.on_timeout(tc.NODES_LD_IH[145][19])
        # THE END
        eq_(self.lookup.num_parallel_queries, 0)
        ok_(self.lookup.is_done)

    def test_dont_query_myself(self):
        logger.debug('test start')
        msg = message.OutgoingGetPeersQuery(tc.CLIENT_ID, tc.INFO_HASH_ZERO)
        expected = [Query(msg, tc.NODES_LD_IH[159][0]),
                    Query(msg, tc.NODES_LD_IH[158][1]),
                    Query(msg, tc.NODES_LD_IH[157][3]),
                    Query(msg, tc.NODES_LD_IH[155][4]),]
        result = self.lookup.start()

        return

        
        for i, r, e in zip(range(len(result)), result, expected):
            eq_(r.msg.info_hash, e.msg.info_hash)
            eq_(r.dstnode, e.dstnode)

            
#OUTDATED!!!!!!!!!!!!!!!!!!!!!!!!!
            
        # Ongoing queries to (sorted: oldest first):
        # 155-4, 157-3, 
        # Queued nodes to query (sorted by log_distance to info_hash):
        # 158-1, 159-0
        # Notice 159-2 is kicked out from the queue
        eq_(self.lookup.num_parallel_queries, 4)
        nodes = [Node(tc.CLIENT_ADDR, self.lookup._my_id)]
        self.lookup.on_response_received(*_gen_nodes_args(
                tc.NODES_LD_IH[157][3],
                nodes))


        return


    
        
        eq_(self.lookup._get_announce_candidates(),
            [tc.NODES_LD_IH[157][3],
             ])
        # This response triggers a new query to 158-1 (ignoring myself)
        eq_(self.lookup.num_parallel_queries, 2)
        # Ongoing queries to (sorted: oldest first):
        # 155-4, 158-1
        # Queued nodes to query (sorted by log_distance to info_hash):
        # 159-0
        self.lookup.on_timeout(tc.NODES_LD_IH[155][4])
        # This timeout triggers a new query (to 159-0)
        eq_(self.lookup.num_parallel_queries, 2) 
        self.lookup.on_timeout(tc.NODES_LD_IH[158][1])
        # No more nodes to send queries to
        eq_(self.lookup.num_parallel_queries, 1)
        ok_(not self.lookup.is_done)
        self.lookup.on_timeout(tc.NODES_LD_IH[159][0]) 
        # No more nodes to send queries to
        eq_(self.lookup.num_parallel_queries, 0)
        ok_(self.lookup.is_done)

        
class _TestLookupManager:

    def _on_got_peers(self, peers):
        self.got_peers = peers
    
    
    def setup(self):
        self.got_peers = None
        querier_ = querier.Querier(tc.CLIENT_ID)
        routing_m = RoutingManagerMock()
        self.bootstrap_nodes = routing_m.get_closest_rnodes(
            tc.INFO_HASH_ZERO)
        self.lm = lookup_manager.LookupManager(tc.CLIENT_ID,
                                               querier_,
                                               routing_m,
                                               2)
        self.lookup = self.lm.get_peers(tc.INFO_HASH, self._on_got_peers,
                                   tc.BT_PORT)

    def test_all_nodes_timeout(self):
        for node_ in self.bootstrap_nodes:
            self.lookup.on_timeout(node_)
        ok_(self.lookup.is_done)

    def test_peers(self):
        self.lookup.on_response_received(*_gen_peers_args(
                self.bootstrap_nodes[0],
                [tc.NO_ADDR]))
        for node_ in self.bootstrap_nodes[1:]:
            self.lookup.on_timeout(node_)
        ok_(self.lookup.is_done)
    def teardown(self):
        self.lm.stop()
        
def _gen_nodes_args(node_, nodes):
    out_msg = message.OutgoingGetPeersResponse(
        node_.id,
        tc.TOKEN,
        nodes2=nodes).encode(tc.TID)
    in_msg = message.IncomingMsg(out_msg, tc.SERVER_ADDR)
    in_msg.sanitize_response(message.GET_PEERS)
    return in_msg, node_

def _gen_peers_args(node_, peers):
    out_msg = message.OutgoingGetPeersResponse(
        node_.id,
        tc.TOKEN,
        peers=peers).encode(tc.TID)
    in_msg = message.IncomingMsg(out_msg, tc.SERVER_ADDR)
    in_msg.sanitize_response(message.GET_PEERS)
    return in_msg, node_

