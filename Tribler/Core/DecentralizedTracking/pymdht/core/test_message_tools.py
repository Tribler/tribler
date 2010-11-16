# Copyright (C) 2009-2010 Raul Jimenez
# Released under GNU LGPL 2.1
# See LICENSE.txt for more information

from nose.tools import ok_, eq_, assert_raises

from socket import inet_aton

import node
import logging, logging_conf

import test_const as tc
import bencode
import message as m
import message_tools as mt

logging_conf.testing_setup(__name__)
logger = logging.getLogger('dht')


class TestMsgTools:

    def setup(self):
        pass

    def test_tools(self):
        bin_strs = ['23', '\1\5', 'a\3']
        for bs in bin_strs:
            i = mt.bin_to_int(bs)
            bs2 = mt.int_to_bin(i)
            logger.debug('bs: %s, bin_to_int(bs): %d, bs2: %s' % (bs,
                                                                   i, bs2))
            assert bs == bs2

        ips = ['127.0.0.1', '222.222.222.222', '1.2.3.4']
        ports = [12345, 99, 54321] 
        for addr in zip(ips, ports):
            c_addr = mt.compact_addr(addr)
            addr2 = mt.uncompact_addr(c_addr)
            assert addr == addr2

            c_peers = mt.compact_peers(tc.PEERS)
            peers = mt.uncompact_peers(c_peers)
            for p1, p2 in zip(tc.PEERS, peers):
                assert p1[0] == p2[0]
                assert p1[0] == p2[0]
            
            c_nodes = mt.compact_nodes(tc.NODES)
            nodes = mt.uncompact_nodes(c_nodes)
            for n1, n2 in zip(tc.NODES, nodes):
                assert n1 == n2

        bin_ipv6s = ['\x00' * 10 + '\xff\xff' + '\1\2\3\4',
                     '\x22' * 16,
                     ]
        #assert mt.bin_to_ip(bin_ipv6s[0]) == '1.2.3.4'
        #assert_raises(mt.AddrError, mt.bin_to_ip, bin_ipv6s[1])


        IP = '1.2.3.4'
        PORT = 7777
        BIN_PORT = mt.int_to_bin(PORT)
        c_nodes2 = [tc.CLIENT_ID.bin_id + inet_aton(IP) + BIN_PORT]
        nodes2 = [node.Node((IP, PORT), tc.CLIENT_ID)]
        logger.debug(mt.uncompact_nodes2(c_nodes2))
        eq_(mt.uncompact_nodes2(c_nodes2), nodes2)
        logger.warning(
            "**IGNORE WARNING LOG** This exception was raised by a test")
       

    def test_tools_error(self):
        c_nodes = mt.compact_nodes(tc.NODES)
        # Compact nodes is one byte short
        eq_(mt.uncompact_nodes(c_nodes[:-1]), [])
        # Port is 0 (
        eq_(mt.uncompact_nodes(c_nodes), tc.NODES)

        nodes = [n for n in tc.NODES]
        # One address has port ZERO
        nodes[0] = node.Node((nodes[0].addr[0], 0), nodes[0].id)
        peers = [n.addr for n in nodes]

        c_nodes = mt.compact_nodes(nodes)
        eq_(mt.uncompact_nodes(c_nodes), nodes[1:])
        c_nodes2 = mt.compact_nodes2(nodes)
        eq_(mt.uncompact_nodes2(c_nodes2), nodes[1:])
        c_peers = mt.compact_peers(peers)
        eq_(mt.uncompact_peers(c_peers), peers[1:])

        
