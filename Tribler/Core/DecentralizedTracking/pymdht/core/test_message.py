# Copyright (C) 2009-2010 Raul Jimenez
# Released under GNU LGPL 2.1
# See LICENSE.txt for more information

from nose.tools import ok_, eq_, assert_raises

import node
import logging, logging_conf

import test_const as tc
import bencode
import message as m
import message_tools as mt

logging_conf.testing_setup(__name__)
logger = logging.getLogger('dht')

def test_matching_tid():
    # It _only_ matches the first byte)
    ok_(m.matching_tid('aaa', 'aaa'))
    ok_(m.matching_tid('axa', 'a1a'))
    ok_(m.matching_tid('aQWEREWTWETWTWETWETEWT', 'a'))
    ok_(not m.matching_tid('a', 'b'))
    ok_(not m.matching_tid('aZZ', 'bZZ'))



class TestMsgExchanges:

    def test_msg_exhanges(self):
        self._exchange_msgs(m.OutgoingPingQuery(tc.CLIENT_ID),
                            m.OutgoingPingResponse(tc.SERVER_ID))

        self._exchange_msgs(m.OutgoingFindNodeQuery(tc.CLIENT_ID,
                                                    tc.TARGET_ID),
                            m.OutgoingFindNodeResponse(tc.SERVER_ID,
                                                       tc.NODES))

        # Test different combinations of token, nodes and peers
        self._exchange_msgs(m.OutgoingGetPeersQuery(tc.CLIENT_ID,
                                                    tc.INFO_HASH),
                            m.OutgoingGetPeersResponse(tc.SERVER_ID,
                                                       tc.TOKEN,
                                                       tc.NODES,
                                                       tc.PEERS))
        self._exchange_msgs(m.OutgoingGetPeersQuery(tc.CLIENT_ID,
                                                    tc.INFO_HASH),
                            m.OutgoingGetPeersResponse(tc.SERVER_ID,
                                                       tc.TOKEN,
                                                       tc.NODES))
        self._exchange_msgs(m.OutgoingGetPeersQuery(tc.CLIENT_ID,
                                                    tc.INFO_HASH),
                            m.OutgoingGetPeersResponse(tc.SERVER_ID,
                                                       tc.TOKEN,
                                                       peers=tc.PEERS))
        assert_raises(AssertionError,
                      m.OutgoingGetPeersResponse,
                      tc.SERVER_ID, tc.TOKEN)
        self._exchange_msgs(m.OutgoingGetPeersQuery(tc.CLIENT_ID,
                                                    tc.INFO_HASH),
                            m.OutgoingGetPeersResponse(tc.SERVER_ID,
                                                       peers=tc.PEERS))
        self._exchange_msgs(m.OutgoingGetPeersQuery(tc.CLIENT_ID,
                                                    tc.INFO_HASH),
                            m.OutgoingGetPeersResponse(tc.SERVER_ID,
                                                       nodes=tc.NODES))
        self._exchange_msgs(m.OutgoingGetPeersQuery(tc.CLIENT_ID,
                                                    tc.INFO_HASH),
                            m.OutgoingGetPeersResponse(tc.SERVER_ID,
                                                       nodes=tc.NODES,
                                                       peers=tc.PEERS))
        assert_raises(AssertionError, m.OutgoingGetPeersResponse,
                      tc.SERVER_ID)

        self._exchange_msgs(m.OutgoingAnnouncePeerQuery(tc.CLIENT_ID,
                                                        tc.INFO_HASH,
                                                        tc.BT_PORT,
                                                        tc.TOKEN),
                            m.OutgoingAnnouncePeerResponse(tc.SERVER_ID))

    def _exchange_msgs(self, outgoing_query, outgoing_response):
        #client
        data = outgoing_query.encode(tc.TID) # querier.register_query()
        #server
        incoming_query = m.IncomingMsg(data, tc.CLIENT_ADDR)
        eq_(incoming_query.type, m.QUERY)
        data = outgoing_response.encode(incoming_query.tid)
        #client
        incoming_response = m.IncomingMsg(data, tc.SERVER_ADDR)
        assert incoming_response.type is m.RESPONSE


class TestEvilIncomingQueries: #aka invalid bencode messages

    bad_non_empty_string = ['', # empty string
                                 123, # integer
                                 [], # list
                                 {}, # dict
                                 ]

    def setup(self): 
        self.queries = [m.OutgoingPingQuery(tc.CLIENT_ID),
                        m.OutgoingFindNodeQuery(tc.CLIENT_ID,
                                                tc.TARGET_ID),
                        m.OutgoingGetPeersQuery(tc.CLIENT_ID,
                                                tc.INFO_HASH),
                        m.OutgoingAnnouncePeerQuery(tc.CLIENT_ID,
                                                    tc.INFO_HASH,
                                                    tc.BT_PORT,
                                                    tc.TOKEN),
                        ]
        self.responses = [m.OutgoingPingResponse(tc.SERVER_ID),
                          m.OutgoingFindNodeResponse(tc.SERVER_ID,
                                                     tc.NODES),
                          m.OutgoingGetPeersResponse(tc.SERVER_ID,
                                                     tc.TOKEN,
                                                     tc.NODES,
                                                     tc.PEERS),
                          m.OutgoingAnnouncePeerResponse(tc.SERVER_ID),
                          ]
    
    def test_bad_bencode(self):
        bencodes = ('11', '11:', '2:zzz', 'a', # invalid bencode
                    'l'*20 + 'e'*20, # invalid bencode (recursivity)
                    'li1ee', 'i1e', '1:a', 'llee', # not a dictionary
                    'de', # empty dictionary
                    )
        for data in bencodes:
            assert_raises(m.MsgError, m.IncomingMsg, data, tc.CLIENT_ADDR)


    def test_bad_tids(self):
        for msg in self.queries + self.responses:
            # no tid
            # msg.encode adds tid
            # a direct encode of the msg._dict produces bencode without tid
            data = bencode.encode(msg._dict)
            assert_raises(m.MsgError, m.IncomingMsg, data, tc.CLIENT_ADDR)
            # tid must be a non-empty string
            bad_tids = self.bad_non_empty_string
            print bad_tids
            for tid in bad_tids:
                self._check_bad_msg(msg, tid)

    def test_bad_types(self):
        for msg in self.queries + self.responses:
            # no type
            del msg._dict[m.TYPE]
            self._check_bad_msg(msg)
            # type must be one of these characters: qre
            bad_types = self.bad_non_empty_string + ['zz', 'a']
            for t in bad_types:
                msg._dict[m.TYPE] = t
                self._check_bad_msg(msg)
        return

    def test_bad_version(self):
        return
             
    def _check_bad_msg(self, msg, tid=tc.TID):
        data = msg.encode(tid)
        assert_raises(m.MsgError, m.IncomingMsg, data, tc.CLIENT_ADDR)
    '''    
    def _test_ping_error(self):
        outgoing_query = m.OutgoingPingQuery(tc.CLIENT_ID)
        outgoing_query.tid = tc.TID
        # TID and ARGS ID are None
        assert_raises(m.MsgError, outgoing_query.encode)
        logger.error(
            "**IGNORE 2 ERROR LOGS** This exception was raised by a test")

        outgoing_query = m.OutgoingPingQuery()
        outgoing_query.my_id = tc.CLIENT_ID
        #outgoing_query.tid = tc.TID
        assert_raises(m.MsgError, outgoing_query.encode)
        logger.error(
            "**IGNORE 2 ERROR LOGS** This exception was raised by a test")

        outgoing_query = m.OutgoingPingQuery()
        #outgoing_query.my_id = tc.CLIENT_ID
        outgoing_query.tid = tc.TID
        assert_raises(m.MsgError, outgoing_query.encode)
        logger.error(
            "**IGNORE 2 ERROR LOGS** This exception was raised by a test")
        
        outgoing_query = m.OutgoingPingQuery()
        assert_raises(m.MsgError, outgoing_query.__setattr__, 'my_id', '')
        logger.error(
            "**IGNORE 2 ERROR LOGS** This exception was raised by a test")
                
        outgoing_query = m.OutgoingPingQuery()
        outgoing_query.my_id = tc.CLIENT_ID
        outgoing_query.tid = 567
        data = outgoing_query.encode()
        assert_raises(m.MsgError, m.decode, data)
        logger.error(
            "**IGNORE 2 ERROR LOGS** This exception was raised by a test")

        outgoing_query = m.OutgoingPingQuery()
        outgoing_query.my_id = tc.CLIENT_ID
        outgoing_query.tid = tc.TID
        data = outgoing_query.encode()
        data += 'this string ruins the bencoded msg'
        assert_raises(m.MsgError, m.decode, data)
        logger.error(
            "**IGNORE 2 ERROR LOGS** This exception was raised by a test")



        
        outgoing_response = m.OutgoingPingResponse(tc.TID, tc.SERVER_ID)
        outgoing_response.tid = None
        assert_raises(m.MsgError, outgoing_response.encode)
        logger.error(
            "**IGNORE ERROR LOGS** This exception was raised by a test")
            '''
    
    def test_find_node(self):
        #client
        outgoing_query = m.OutgoingFindNodeQuery(tc.CLIENT_ID, tc.NODE_ID)
        data = outgoing_query.encode(tc.TID)
        #server
        incoming_query = m.IncomingMsg(data, tc.CLIENT_ADDR)
        assert incoming_query.type is m.QUERY
        outgoing_response = m.OutgoingFindNodeResponse(tc.SERVER_ID,
                                                     tc.NODES)
        data = outgoing_response.encode(incoming_query.tid)
        #client
        incoming_response = m.IncomingMsg(data, tc.SERVER_ADDR)
        eq_(incoming_response.type, m.RESPONSE)
        #incoming_response.sanitize_response(outgoing_query.query)
        for n1, n2 in zip(tc.NODES, incoming_response.all_nodes):
            eq_(n1, n2)


    def _test_find_node_error(self):
        #assert_raises(m.MsgError, m.OutgoingFindNodeResponse,
        #              tc.CLIENT_ID, nodes=tc.NODES)
        assert_raises(m.MsgError, m.OutgoingFindNodeResponse,
                      tc.CLIENT_ID)

        
    def test_get_peers_nodes(self):
        #client
        outgoing_query = m.OutgoingGetPeersQuery(tc.CLIENT_ID, tc.INFO_HASH)
        data = outgoing_query.encode(tc.TID)
        #server
        incoming_query = m.IncomingMsg(data, tc.CLIENT_ADDR)
        assert incoming_query.type is m.QUERY
        outgoing_response = m.OutgoingGetPeersResponse(tc.SERVER_ID,
                                                     tc.TOKEN,
                                                     tc.NODES)
        data = outgoing_response.encode(incoming_query.tid)
        #client
        incoming_response = m.IncomingMsg(data, tc.SERVER_ADDR)
        assert incoming_response.type is m.RESPONSE
        #incoming_response.sanitize_response(outgoing_query.query)
        for n1, n2 in zip(tc.NODES, incoming_response.all_nodes):
            assert n1 == n2

    def test_get_peers_peers(self):
        #client
        outgoing_query = m.OutgoingGetPeersQuery(tc.CLIENT_ID, tc.INFO_HASH)
        data = outgoing_query.encode(tc.TID)
        #server
        incoming_query = m.IncomingMsg(data, tc.CLIENT_ADDR)
        assert incoming_query.type is m.QUERY
        outgoing_response = m.OutgoingGetPeersResponse(tc.SERVER_ID,
                                                       tc.TOKEN,
                                                       tc.NODES,
                                                       tc.PEERS)
        data = outgoing_response.encode(incoming_query.tid)
        #client
        incoming_response = m.IncomingMsg(data, tc.SERVER_ADDR)
        assert incoming_response.type is m.RESPONSE
        #incoming_response.sanitize_response(outgoing_query.query)
        for p1, p2 in zip(tc.PEERS, incoming_response.peers):
            assert p1[0] == p2[0]
            assert p1[1] == p2[1]

    def test_get_peers_peers_error(self):
        assert 1

    def test_announce_peer(self):
        #client
        outgoing_query = m.OutgoingAnnouncePeerQuery(tc.CLIENT_ID,
                                                   tc.INFO_HASH,
                                                   tc.BT_PORT,
                                                   tc.TOKEN)
        outgoing_query.tid = tc.TID
        data = outgoing_query.encode(tc.TID)
        #server
        incoming_query = m.IncomingMsg(data, tc.CLIENT_ADDR)
        assert incoming_query.type is m.QUERY
        outgoing_response = m.OutgoingAnnouncePeerResponse(tc.SERVER_ID)
        data = outgoing_response.encode(incoming_query.tid)
        #client
        incoming_response = m.IncomingMsg(data, tc.SERVER_ADDR)
        assert incoming_response.type is m.RESPONSE
        #incoming_response.sanitize_response(outgoing_query.query)

    def test_announce_peer_error(self):
        assert 1
    '''
    def _test_error(self):
        outgoing_error_msg = m.OutgoingErrorMsg(tc.TID, m.GENERIC_E)
        data = outgoing_error_msg.encode()
        tid, msg_type, msg_dict = m.decode(data)
        incoming_error_msg = m.IncomingErrorMsg(msg_dict)
        logger.debug(incoming_error_msg.error)
        assert incoming_error_msg.error == m.GENERIC_E
    '''

def value_is_string(msg_d, k, valid_values=None):
    v = msg_d[k]
    ok_(isinstance(v, str))
    
        

class TestIncomingMsg:

    def setup(self):
        b_ping = m.OutgoingPingQuery(tc.CLIENT_ID).encode(tc.TID)
        self.msg_d = m.IncomingMsg(b_ping, tc.CLIENT_ADDR)._msg_dict


    def test_tid_error(self):
        # no TID
        del self.msg_d[m.TID] 
        assert_raises(m.MsgError, m.IncomingMsg,
                      bencode.encode(self.msg_d), tc.CLIENT_ADDR)
        # invalid m.TID
        self.msg_d[m.TID] = 1
        assert_raises(m.MsgError, m.IncomingMsg,
                      bencode.encode(self.msg_d), tc.CLIENT_ADDR)
        self.msg_d[m.TID] = []
        assert_raises(m.MsgError, m.IncomingMsg,
                      bencode.encode(self.msg_d), tc.CLIENT_ADDR)
        self.msg_d[m.TID] = {}
        assert_raises(m.MsgError, m.IncomingMsg,
                      bencode.encode(self.msg_d), tc.CLIENT_ADDR)
        
    def test_type_error(self):
        # no TYPE
        del self.msg_d[m.TYPE] 
        assert_raises(m.MsgError, m.IncomingMsg,
                      bencode.encode(self.msg_d), tc.CLIENT_ADDR)
        # invalid m.TYPE
        self.msg_d[m.TYPE] = 1
        assert_raises(m.MsgError, m.IncomingMsg,
                      bencode.encode(self.msg_d), tc.CLIENT_ADDR)
        self.msg_d[m.TYPE] = []
        assert_raises(m.MsgError, m.IncomingMsg,
                      bencode.encode(self.msg_d), tc.CLIENT_ADDR)
        self.msg_d[m.TYPE] = {}
        assert_raises(m.MsgError, m.IncomingMsg,
                      bencode.encode(self.msg_d), tc.CLIENT_ADDR)
        # unknown m.TYPE
        self.msg_d[m.TYPE] = 'z'
        assert_raises(m.MsgError, m.IncomingMsg,
                      bencode.encode(self.msg_d), tc.CLIENT_ADDR)

    def test_version_not_present(self):
        del self.msg_d[m.VERSION]
        m.IncomingMsg(bencode.encode(self.msg_d), tc.CLIENT_ADDR)

    def test_unknown_error(self):
        error_code = (999, "some weird error string")
        b_err = m.OutgoingErrorMsg(error_code).encode(tc.TID)
        
        logger.info(
            "TEST LOGGING ** IGNORE EXPECTED INFO ** Unknown error: %r",
            error_code)
        _ = m.IncomingMsg(b_err, tc.CLIENT_ADDR)

    def test_nodes2(self):
        response = m.OutgoingGetPeersResponse(tc.CLIENT_ID, peers=tc.PEERS)
        response._dict[m.RESPONSE][m.NODES2] = mt.compact_nodes2(tc.NODES)
        bencoded = response.encode(tc.TID)
        m.IncomingMsg(bencoded, tc.CLIENT_ADDR)


        
b_ping_q = m.OutgoingPingQuery(tc.CLIENT_ID).encode(tc.TID)
b_fn_q = m.OutgoingFindNodeQuery(tc.CLIENT_ID, tc.NODE_ID).encode(tc.TID)
b_gp_q = m.OutgoingGetPeersQuery(tc.CLIENT_ID, tc.INFO_HASH).encode(tc.TID)
b_ap_q = m.OutgoingAnnouncePeerQuery(tc.CLIENT_ID, tc.INFO_HASH,
                                 tc.BT_PORT,tc.TOKEN).encode(tc.TID)

class TestSanitizeQueryError:

    def setup(self):
        self.ping_d = m.IncomingMsg(b_ping_q, tc.CLIENT_ADDR)._msg_dict
        self.fn_d = m.IncomingMsg(b_fn_q, tc.CLIENT_ADDR)._msg_dict
        self.gp_d = m.IncomingMsg(b_gp_q, tc.CLIENT_ADDR)._msg_dict
        self.ap_d = m.IncomingMsg(b_ap_q, tc.CLIENT_ADDR)._msg_dict

    def test_weird_msg(self):
        self.ping_d[m.ARGS] = []
        assert_raises(m.MsgError, m.IncomingMsg,
                      bencode.encode(self.ping_d), tc.CLIENT_ADDR)
        self.ping_d[m.ARGS] = 1
        assert_raises(m.MsgError, m.IncomingMsg,
                      bencode.encode(self.ping_d), tc.CLIENT_ADDR)
        self.ping_d[m.ARGS] = 'ZZZZ'
        assert_raises(m.MsgError, m.IncomingMsg,
                      bencode.encode(self.ping_d), tc.CLIENT_ADDR)
        
        
        
    def test_sender_id(self):
        # no sender_id
        del self.ping_d[m.ARGS][m.ID]
        assert_raises(m.MsgError, m.IncomingMsg,
                      bencode.encode(self.ping_d), tc.CLIENT_ADDR)
        # bad ID
        self.ping_d[m.ARGS][m.ID] = 'a'
        assert_raises(m.MsgError, m.IncomingMsg,
                      bencode.encode(self.ping_d), tc.CLIENT_ADDR)
        self.ping_d[m.ARGS][m.ID] = 1
        assert_raises(m.MsgError, m.IncomingMsg,
                      bencode.encode(self.ping_d), tc.CLIENT_ADDR)
        self.ping_d[m.ARGS][m.ID] = []
        assert_raises(m.MsgError, m.IncomingMsg,
                      bencode.encode(self.ping_d), tc.CLIENT_ADDR)
        self.ping_d[m.ARGS][m.ID] = {}
        assert_raises(m.MsgError, m.IncomingMsg,
                      bencode.encode(self.ping_d), tc.CLIENT_ADDR)

    def test_query(self): 
        # no m.QUERY
        del self.ping_d[m.QUERY]
        assert_raises(m.MsgError, m.IncomingMsg,
                      bencode.encode(self.ping_d), tc.CLIENT_ADDR)
        # bad m.QUERY
        self.ping_d[m.QUERY] = 1
        assert_raises(m.MsgError, m.IncomingMsg,
                      bencode.encode(self.ping_d), tc.CLIENT_ADDR)
        self.ping_d[m.QUERY] = []
        assert_raises(m.MsgError, m.IncomingMsg,
                      bencode.encode(self.ping_d), tc.CLIENT_ADDR)
        self.ping_d[m.QUERY] = {}
        assert_raises(m.MsgError, m.IncomingMsg,
                      bencode.encode(self.ping_d), tc.CLIENT_ADDR)
        # unknown m.QUERY is not an error at this point
        # responder will process it and send an errror msg if necesary
        self.ping_d[m.QUERY] = 'a'
        m.IncomingMsg(bencode.encode(self.ping_d), tc.CLIENT_ADDR)

    def test_announce(self):
        # Port must be integer
        self.ap_d[m.ARGS][m.PORT] = 'a'
        assert_raises(m.MsgError, m.IncomingMsg,
                      bencode.encode(self.ap_d), tc.CLIENT_ADDR)

        
b_ping_r = m.OutgoingPingResponse(tc.CLIENT_ID).encode(tc.TID)
b_fn2_r = m.OutgoingFindNodeResponse(tc.CLIENT_ID, tc.NODES).encode(tc.TID)
b_gp_r = m.OutgoingGetPeersResponse(tc.CLIENT_ID, tc.TOKEN, tc.NODES,
                                    peers=tc.PEERS).encode(tc.TID)
b_ap_r = m.OutgoingAnnouncePeerResponse(tc.CLIENT_ID).encode(tc.TID)

class TestSanitizeResponseError:

    def setup(self):
        self.ping_r = m.IncomingMsg(b_ping_r, tc.SERVER_ADDR)
        self.fn2_r = m.IncomingMsg(b_fn2_r, tc.SERVER_ADDR)
        self.gp_r = m.IncomingMsg(b_gp_r, tc.SERVER_ADDR)
        self.ap_r = m.IncomingMsg(b_ap_r, tc.SERVER_ADDR)
'''
    def _test_sanitize(self):
        self.ping_r.sanitize_response(m.PING)

        del self.fn2_r._msg_dict[m.RESPONSE][m.NODES2]
        # No NODES and no NODES2
        assert_raises(m.MsgError, self.fn2_r.sanitize_response, m.FIND_NODE)
        self.fn2_r._msg_dict[m.RESPONSE][m.NODES] = \
            mt.compact_nodes(tc.NODES)
        # Just NODES
        self.fn2_r.sanitize_response(m.FIND_NODE)
        self.fn2_r._msg_dict[m.RESPONSE][m.NODES2] = \
            mt.compact_nodes2(tc.NODES)
        # Both NODES and NODES2
        self.fn2_r.sanitize_response(m.FIND_NODE)

        # Both NODES and PEERS in response
        self.gp_r._msg_dict[m.RESPONSE][m.NODES] = \
            mt.compact_nodes(tc.NODES)
        self.gp_r.sanitize_response(m.GET_PEERS)
        # No NODES and no PEERS
        del self.gp_r._msg_dict[m.RESPONSE][m.NODES]
        del self.gp_r._msg_dict[m.RESPONSE][m.VALUES]
        assert_raises(m.MsgError, self.gp_r.sanitize_response, m.GET_PEERS)
'''        
        
class TestSanitizeErrorError:

    def test(self):
        msg_out = m.OutgoingErrorMsg(1).encode(tc.TID)
        assert_raises(m.MsgError, m.IncomingMsg, msg_out, tc.CLIENT_ADDR)
        # Unknown error doesn't raise m.MsgError
        msg_out = m.OutgoingErrorMsg((1,1)).encode(tc.TID)
        _ = m.IncomingMsg(msg_out, tc.SERVER_ADDR)
    


        
class TestPrinting:
    
    def test_printing(self):
        out_msg = m.OutgoingPingQuery(tc.CLIENT_ID)
        in_msg = m.IncomingMsg(out_msg.encode(tc.TID), tc.CLIENT_ADDR)
        str(out_msg)
        repr(out_msg)
        repr(in_msg)

                  
class TestPrivateDHT:

    def test(self):
        # Sender doesn't use private flag
        ping_public = m.OutgoingPingQuery(tc.CLIENT_ID)
        bencoded_public = ping_public.encode(tc.TID)
        # Sender uses private flag PRIVATE1
        m.private_dht_name = 'PRIVATE1'
        ping_private1 = m.OutgoingPingQuery(tc.CLIENT_ID)
        bencoded_private1 = ping_private1.encode(tc.TID)
        # Sender uses private flag PRIVATE1
        m.private_dht_name = 'PRIVATE2'
        ping_private2 = m.OutgoingPingQuery(tc.CLIENT_ID)
        bencoded_private2 = ping_private2.encode(tc.TID)

        # Receiver in the public DHT accepts messages (ignores private flag)
        m.private_dht_name = None
        m.IncomingMsg(bencoded_public, tc.CLIENT_ADDR)
        m.IncomingMsg(bencoded_private1, tc.CLIENT_ADDR)
        m.IncomingMsg(bencoded_private2, tc.CLIENT_ADDR)

        # Receiver in the private DHT accepts ONLY messages from the
        # private DHT it belongs to
        m.private_dht_name = 'PRIVATE1'
        assert_raises(m.MsgError,
                      m.IncomingMsg, bencoded_public, tc.CLIENT_ADDR)
        m.IncomingMsg(bencoded_private1, tc.CLIENT_ADDR)
        assert_raises(m.MsgError,
                      m.IncomingMsg, bencoded_private2, tc.CLIENT_ADDR)

    def teardown(self):
        m.private_dht_name = None
