# Copyright (C) 2009 Raul Jimenez
# Released under GNU LGPL 2.1
# See LICENSE.txt for more information

from nose.tools import *

import node
import logging, logging_conf

import test_const as tc
import message
from message import *

logging_conf.testing_setup(__name__)
logger = logging.getLogger('dht')


class TestMsg:

    def setup(self):
        pass

    def test_tools(self):
        bin_strs = ['23', '\1\5', 'a\3']
        for bs in bin_strs:
            i = bin_to_int(bs)
            bs2 = int_to_bin(i)
            logger.debug('bs: %s, bin_to_int(bs): %d, bs2: %s' % (bs,
                                                                   i, bs2))
            assert bs == bs2

        ips = ['127.0.0.1', '222.222.222.222', '1.2.3.4']
        ports = [12345, 99, 54321] 
        for addr in zip(ips, ports):
            c_addr = compact_addr(addr)
            addr2 = uncompact_addr(c_addr)
            assert addr == addr2

            c_peers = message._compact_peers(tc.PEERS)
            peers = message._uncompact_peers(c_peers)
            for p1, p2 in zip(tc.PEERS, peers):
                assert p1[0] == p2[0]
                assert p1[0] == p2[0]
            
            c_nodes = message._compact_nodes(tc.NODES)
            nodes = message._uncompact_nodes(c_nodes)
            for n1, n2 in zip(tc.NODES, nodes):
                assert n1 == n2

        bin_ipv6s = ['\x00' * 10 + '\xff\xff' + '\1\2\3\4',
                     '\x22' * 16,
                     ]
        assert bin_to_ip(bin_ipv6s[0]) == '1.2.3.4'
        assert_raises(AddrError, bin_to_ip, bin_ipv6s[1])


        PORT = 7777
        BIN_PORT = int_to_bin(PORT)
        c_nodes2 = [tc.CLIENT_ID.bin_id + ip + BIN_PORT for ip in bin_ipv6s]
        nodes2 = [node.Node(('1.2.3.4', PORT), tc.CLIENT_ID)]
        logger.debug(message._uncompact_nodes2(c_nodes2))
        assert message._uncompact_nodes2(c_nodes2) == nodes2 
        logger.warning(
            "**IGNORE WARNING LOG** This exception was raised by a test")
       

    def test_tools_error(self):
        c_nodes = message._compact_nodes(tc.NODES)
        # Compact nodes is one byte short
        assert_raises(MsgError, message._uncompact_nodes, c_nodes[:-1])
        # IP size is weird
        assert_raises(MsgError, bin_to_ip, '123')
        # Port is 0 (
        eq_(message._uncompact_nodes(c_nodes), tc.NODES)
        n = tc.NODES[0]
        tc.NODES[0] = node.Node((n.addr[0], 0), n.id)
        c_nodes = message._compact_nodes(tc.NODES)
        eq_(message._uncompact_nodes(c_nodes), tc.NODES[1:])
        c_nodes2 = message._compact_nodes2(tc.NODES)
        eq_(message._uncompact_nodes2(c_nodes2), tc.NODES[1:])
        tc.NODES[0] = n
        
    def test_matching_tid(self):
        # It _only_ matches the first byte)
        ok_(matching_tid('aaa', 'aaa'))
        ok_(matching_tid('axa', 'a1a'))
        ok_(matching_tid('aQWEREWTWETWTWETWETEWT', 'a'))
        ok_(not matching_tid('a', 'b'))
        ok_(not matching_tid('aZZ', 'bZZ'))
        
    def test_ping(self):
        #client
        outgoing_query = OutgoingPingQuery(tc.CLIENT_ID)
        data = outgoing_query.encode(tc.TID) # query_manager would do it
        #server
        incoming_query = IncomingMsg(data)
        assert incoming_query.type is QUERY
        outgoing_response = OutgoingPingResponse(tc.SERVER_ID)
        data = outgoing_response.encode(incoming_query.tid)
        #client
        incoming_response = IncomingMsg(data)
        assert incoming_response.type is RESPONSE
        incoming_response.sanitize_response(outgoing_query.query)

    def _test_ping_error(self):
        outgoing_query = OutgoingPingQuery(tc.CLIENT_ID)
        #outgoing_query.my_id = CLIENT_ID
        #outgoing_query.tid = tc.TID
        # TID and ARGS ID are None
        assert_raises(MsgError, outgoing_query.encode)
        logger.error(
            "**IGNORE 2 ERROR LOGS** This exception was raised by a test")

        outgoing_query = OutgoingPingQuery()
        outgoing_query.my_id = tc.CLIENT_ID
        #outgoing_query.tid = tc.TID
        assert_raises(MsgError, outgoing_query.encode)
        logger.error(
            "**IGNORE 2 ERROR LOGS** This exception was raised by a test")

        outgoing_query = OutgoingPingQuery()
        #outgoing_query.my_id = tc.CLIENT_ID
        outgoing_query.tid = tc.TID
        assert_raises(MsgError, outgoing_query.encode)
        logger.error(
            "**IGNORE 2 ERROR LOGS** This exception was raised by a test")
        
        outgoing_query = OutgoingPingQuery()
        assert_raises(MsgError, outgoing_query.__setattr__, 'my_id', '')
        logger.error(
            "**IGNORE 2 ERROR LOGS** This exception was raised by a test")
                
        outgoing_query = OutgoingPingQuery()
        outgoing_query.my_id = tc.CLIENT_ID
        outgoing_query.tid = 567
        data = outgoing_query.encode()
        assert_raises(MsgError, decode, data)
        logger.error(
            "**IGNORE 2 ERROR LOGS** This exception was raised by a test")

        outgoing_query = OutgoingPingQuery()
        outgoing_query.my_id = tc.CLIENT_ID
        outgoing_query.tid = tc.TID
        data = outgoing_query.encode()
        data += 'this string ruins the bencoded msg'
        assert_raises(MsgError, decode, data)
        logger.error(
            "**IGNORE 2 ERROR LOGS** This exception was raised by a test")



        
        outgoing_response = OutgoingPingResponse(tc.TID, tc.SERVER_ID)
        outgoing_response.tid = None
        assert_raises(MsgError, outgoing_response.encode)
        logger.error(
            "**IGNORE ERROR LOGS** This exception was raised by a test")

            
    def test_find_node(self):
        #client
        outgoing_query = OutgoingFindNodeQuery(tc.CLIENT_ID, tc.NODE_ID)
        data = outgoing_query.encode(tc.TID)
        #server
        incoming_query = IncomingMsg(data)
        assert incoming_query.type is QUERY
        outgoing_response = OutgoingFindNodeResponse(tc.SERVER_ID,
                                                     tc.NODES)
        data = outgoing_response.encode(incoming_query.tid)
        #client
        incoming_response = IncomingMsg(data)
        eq_(incoming_response.type, RESPONSE)
        incoming_response.sanitize_response(outgoing_query.query)
        for n1, n2 in zip(tc.NODES, incoming_response.nodes2):
            eq_(n1, n2)


    def test_find_node_error(self):
        assert_raises(MsgError, OutgoingFindNodeResponse,
                      tc.CLIENT_ID, nodes=tc.NODES)
        assert_raises(MsgError, OutgoingFindNodeResponse,
                      tc.CLIENT_ID)

        
    def test_get_peers_nodes(self):
        #client
        outgoing_query = OutgoingGetPeersQuery(tc.CLIENT_ID, tc.INFO_HASH)
        data = outgoing_query.encode(tc.TID)
        #server
        incoming_query = IncomingMsg(data)
        assert incoming_query.type is QUERY
        outgoing_response = OutgoingGetPeersResponse(tc.SERVER_ID,
                                                     tc.TOKEN,
                                                     nodes2=tc.NODES)
        data = outgoing_response.encode(incoming_query.tid)
        #client
        incoming_response = IncomingMsg(data)
        assert incoming_response.type is RESPONSE
        incoming_response.sanitize_response(outgoing_query.query)
        for n1, n2 in zip(tc.NODES, incoming_response.nodes2):
            assert n1 == n2

    def test_get_peers_nodes_error(self):
        assert_raises(MsgError, OutgoingGetPeersResponse,
                      tc.CLIENT_ID, tc.TOKEN)
                        
    def test_get_peers_peers(self):
        #client
        outgoing_query = OutgoingGetPeersQuery(tc.CLIENT_ID, tc.INFO_HASH)
        data = outgoing_query.encode(tc.TID)
        #server
        incoming_query = IncomingMsg(data)
        assert incoming_query.type is QUERY
        outgoing_response = OutgoingGetPeersResponse(tc.SERVER_ID,
                                                     tc.TOKEN,
                                                     peers=tc.PEERS)
        data = outgoing_response.encode(incoming_query.tid)
        #client
        incoming_response = IncomingMsg(data)
        assert incoming_response.type is RESPONSE
        incoming_response.sanitize_response(outgoing_query.query)
        for p1, p2 in zip(tc.PEERS, incoming_response.peers):
            assert p1[0] == p2[0]
            assert p1[1] == p2[1]

    def test_get_peers_peers_error(self):
        assert 1

    def test_announce_peer(self):
        #client
        outgoing_query = OutgoingAnnouncePeerQuery(tc.CLIENT_ID,
                                                   tc.INFO_HASH,
                                                   tc.BT_PORT,
                                                   tc.TOKEN)
        outgoing_query.tid = tc.TID
        data = outgoing_query.encode(tc.TID)
        #server
        incoming_query = IncomingMsg(data)
        assert incoming_query.type is QUERY
        outgoing_response = OutgoingAnnouncePeerResponse(tc.SERVER_ID)
        data = outgoing_response.encode(incoming_query.tid)
        #client
        incoming_response = IncomingMsg(data)
        assert incoming_response.type is RESPONSE
        incoming_response.sanitize_response(outgoing_query.query)

    def test_announce_peer_error(self):
        assert 1

    def _test_error(self):
        outgoing_error_msg = OutgoingErrorMsg(tc.TID, GENERIC_E)
        data = outgoing_error_msg.encode()
        tid, msg_type, msg_dict = decode(data)
        incoming_error_msg = IncomingErrorMsg(msg_dict)
        logger.debug(incoming_error_msg.error)
        assert incoming_error_msg.error == GENERIC_E


def value_is_string(msg_d, k, valid_values=None):
    v = msg_d[k]
    ok_(isinstance(v, str))
    
        

class TestIncomingMsg:

    def setup(self):
        b_ping = OutgoingPingQuery(tc.CLIENT_ID).encode(tc.TID)
        self.msg_d = IncomingMsg(b_ping)._msg_dict

    def test_bad_bencode(self):
        assert_raises(MsgError, IncomingMsg, 'z')
        assert_raises(MsgError, IncomingMsg, '1:aa')
        assert_raises(MsgError, IncomingMsg, 'd')

    def test_not_a_dict(self):
        msgs = ([], 'a', 1)
        for msg in msgs:               
            assert_raises(MsgError, IncomingMsg, bencode.encode(msg))

    def test_tid_error(self):
        # no TID
        del self.msg_d[TID] 
        assert_raises(MsgError, IncomingMsg, bencode.encode(self.msg_d))
        # invalid TID
        self.msg_d[TID] = 1
        assert_raises(MsgError, IncomingMsg, bencode.encode(self.msg_d))
        self.msg_d[TID] = []
        assert_raises(MsgError, IncomingMsg, bencode.encode(self.msg_d))
        self.msg_d[TID] = {}
        assert_raises(MsgError, IncomingMsg, bencode.encode(self.msg_d))
        
    def test_type_error(self):
        # no TYPE
        del self.msg_d[TYPE] 
        assert_raises(MsgError, IncomingMsg, bencode.encode(self.msg_d))
        # invalid TYPE
        self.msg_d[TYPE] = 1
        assert_raises(MsgError, IncomingMsg, bencode.encode(self.msg_d))
        self.msg_d[TYPE] = []
        assert_raises(MsgError, IncomingMsg, bencode.encode(self.msg_d))
        self.msg_d[TYPE] = {}
        assert_raises(MsgError, IncomingMsg, bencode.encode(self.msg_d))
        # unknown TYPE
        self.msg_d[TYPE] = 'z'
        assert_raises(MsgError, IncomingMsg, bencode.encode(self.msg_d))

    def test_version_not_present(self):
        del self.msg_d[VERSION]
        IncomingMsg(bencode.encode(self.msg_d))

    def test_unknown_error(self):
        error_code = (999, "some weird error string")
        b_err = OutgoingErrorMsg(error_code).encode(tc.TID)
        
        logger.info(
            "TEST LOGGING ** IGNORE EXPECTED INFO ** Unknown error: %r",
            error_code)
        _ = IncomingMsg(b_err)


        
b_ping_q = OutgoingPingQuery(tc.CLIENT_ID).encode(tc.TID)
b_fn_q = OutgoingFindNodeQuery(tc.CLIENT_ID, tc.NODE_ID).encode(tc.TID)
b_gp_q = OutgoingGetPeersQuery(tc.CLIENT_ID, tc.INFO_HASH).encode(tc.TID)
b_ap_q = OutgoingAnnouncePeerQuery(tc.CLIENT_ID, tc.INFO_HASH,
                                 tc.BT_PORT,tc.TOKEN).encode(tc.TID)

class TestSanitizeQueryError:

    def setup(self):
        self.ping_d = IncomingMsg(b_ping_q)._msg_dict
        self.fn_d = IncomingMsg(b_fn_q)._msg_dict
        self.gp_d = IncomingMsg(b_gp_q)._msg_dict
        self.ap_d = IncomingMsg(b_ap_q)._msg_dict

    def test_weird_msg(self):
        self.ping_d[ARGS] = []
        assert_raises(MsgError, IncomingMsg, bencode.encode(self.ping_d))
        self.ping_d[ARGS] = 1
        assert_raises(MsgError, IncomingMsg, bencode.encode(self.ping_d))
        self.ping_d[ARGS] = 'ZZZZ'
        assert_raises(MsgError, IncomingMsg, bencode.encode(self.ping_d))
        
        
        
    def test_sender_id(self):
        # no sender_id
        del self.ping_d[ARGS][ID]
        assert_raises(MsgError, IncomingMsg, bencode.encode(self.ping_d))
        # bad ID
        self.ping_d[ARGS][ID] = 'a'
        assert_raises(MsgError, IncomingMsg, bencode.encode(self.ping_d))
        self.ping_d[ARGS][ID] = 1
        assert_raises(MsgError, IncomingMsg, bencode.encode(self.ping_d))
        self.ping_d[ARGS][ID] = []
        assert_raises(MsgError, IncomingMsg, bencode.encode(self.ping_d))
        self.ping_d[ARGS][ID] = {}
        assert_raises(MsgError, IncomingMsg, bencode.encode(self.ping_d))

    def test_query(self): 
        # no QUERY
        del self.ping_d[QUERY]
        assert_raises(MsgError, IncomingMsg, bencode.encode(self.ping_d))
        # bad QUERY
        self.ping_d[QUERY] = 1
        assert_raises(MsgError, IncomingMsg, bencode.encode(self.ping_d))
        self.ping_d[QUERY] = []
        assert_raises(MsgError, IncomingMsg, bencode.encode(self.ping_d))
        self.ping_d[QUERY] = {}
        assert_raises(MsgError, IncomingMsg, bencode.encode(self.ping_d))
        # unknown QUERY is not an error at this point
        # responder will process it and send an errror msg if necesary
        self.ping_d[QUERY] = 'a'
        IncomingMsg(bencode.encode(self.ping_d))

    def test_announce(self):
        # Port must be integer
        self.ap_d[ARGS][PORT] = 'a'
        assert_raises(MsgError, IncomingMsg, bencode.encode(self.ap_d))

        
b_ping_r = OutgoingPingResponse(tc.CLIENT_ID).encode(tc.TID)
b_fn2_r = OutgoingFindNodeResponse(tc.CLIENT_ID, nodes2=tc.NODES).encode(tc.TID)
b_gp_r = OutgoingGetPeersResponse(tc.CLIENT_ID, token=tc.TOKEN,
                                peers=tc.PEERS).encode(tc.TID)
b_ap_r = OutgoingAnnouncePeerResponse(tc.CLIENT_ID).encode(tc.TID)

class TestSanitizeResponseError:

    def setup(self):
        self.ping_r = IncomingMsg(b_ping_r)
        self.fn2_r = IncomingMsg(b_fn2_r)
        self.gp_r = IncomingMsg(b_gp_r)
        self.ap_r = IncomingMsg(b_ap_r)

    def test_nodes_not_implemented(self):
        assert_raises(MsgError, OutgoingFindNodeResponse, tc.CLIENT_ID,
                                        nodes=tc.NODES)
    def test_sanitize(self):
        self.ping_r.sanitize_response(PING)

        del self.fn2_r._msg_dict[RESPONSE][NODES2]
        # No NODES and no NODES2
        assert_raises(MsgError, self.fn2_r.sanitize_response, FIND_NODE)
        self.fn2_r._msg_dict[RESPONSE][NODES] = \
            message._compact_nodes(tc.NODES)
        # Just NODES
        self.fn2_r.sanitize_response(FIND_NODE)
        self.fn2_r._msg_dict[RESPONSE][NODES2] = \
            message._compact_nodes2(tc.NODES)
        # Both NODES and NODES2
        self.fn2_r.sanitize_response(FIND_NODE)

        # Both NODES and PEERS in response
        self.gp_r._msg_dict[RESPONSE][NODES] = \
            message._compact_nodes(tc.NODES)
        self.gp_r.sanitize_response(GET_PEERS)
        # No NODES and no PEERS
        del self.gp_r._msg_dict[RESPONSE][NODES]
        del self.gp_r._msg_dict[RESPONSE][VALUES]
        assert_raises(MsgError, self.gp_r.sanitize_response, GET_PEERS)
        
        
class TestSanitizeErrorError:

    def test(self):
        msg_out = OutgoingErrorMsg(1).encode(tc.TID)
        assert_raises(MsgError, IncomingMsg, msg_out)
        # Unknown error doesn't raise MsgError
        msg_out = OutgoingErrorMsg((1,1)).encode(tc.TID)
        _ = IncomingMsg(msg_out)
    


        
class TestPrinting:
    
    def test_printing(self):
        out_msg = OutgoingPingQuery(tc.CLIENT_ID)
        in_msg = IncomingMsg(out_msg.encode(tc.TID))
        str(out_msg)
        repr(out_msg)
        repr(in_msg)
    
                  
