# Written by Arno Bakker
# see LICENSE.txt for license information

import sys

from Tribler.Test.test_permid import TestPermIDs
from btconn import BTConnection
from Tribler.Core.BitTornado.bencode import bencode, bdecode
from Tribler.Core.BitTornado.BT1.MessageID import *
from Tribler.Core.Utilities.Crypto import sha

DEBUG=False

cr_random_size = 1024

class OLConnection:

    def __init__(self,my_keypair,hostname,port,opensock=None,mylistenport=481,myoversion=None):
        """ If opensock is not None, we assume this is a connection we
            accepted, and he initiates the Challenge/Response
        """

        self.my_keypair = my_keypair
        self.b = BTConnection(hostname,port,opensock,mylistenport=mylistenport,myoversion=myoversion)
        if opensock:
            self.b.read_handshake_medium_rare()
            # Read challenge
            msg = self.b.recv()
            assert(msg[0] == CHALLENGE)
            randomB = bdecode(msg[1:])
            [randomA,resp1_data] = self.create_good_response1(randomB,self.b.get_his_id())
            self.b.send(resp1_data)
            # Read response2
            msg = self.b.recv()
            assert(msg[0] == RESPONSE2)
        else:
            self.b.read_handshake()
            [rB,chal_data] = self.create_good_challenge()
            self.b.send(chal_data)
            resp1_data = self.b.recv()
            if DEBUG:
                print >>sys.stderr,"olconn: recv",len(resp1_data),"bytes"
            resp1_dict = bdecode(resp1_data[1:])
            resp2_data = self.create_good_response2(rB,resp1_dict,self.b.get_his_id())
            self.b.send(resp2_data)
            if DEBUG:
                print >>sys.stderr,"olconn: sent",len(resp2_data),"bytes"

    def get_my_fake_listen_port(self):
        return self.b.get_my_fake_listen_port()

    #
    # Cut 'n paste from TestPermIDs 
    #
    def create_good_challenge(self):
        r = "".zfill(cr_random_size)
        return [r,self.create_challenge_payload(r)]

    def create_good_response2(self,rB,resp1_dict,hisid):
        resp2 = {}
        resp2['certB'] = str(self.my_keypair.pub().get_der())
        resp2['A'] = hisid
        sig_list = [rB,resp1_dict['rA'],hisid]
        sig_data = bencode(sig_list)
        sig_hash = sha(sig_data).digest()
        sig_asn1 = str(self.my_keypair.sign_dsa_asn1(sig_hash))
        resp2['SB'] = sig_asn1
        return self.create_response2_payload(resp2)

    def create_challenge_payload(self,r):
        return CHALLENGE+bencode(r)

    def create_response2_payload(self,dict):
        return RESPONSE2+bencode(dict)


    #
    # Cut 'n paste from TestPermIDResponse1
    #
    def create_good_response1(self,rB,hisid):
        resp1 = {}
        resp1['certA'] = str(self.my_keypair.pub().get_der())
        resp1['rA'] = "".zfill(cr_random_size)
        resp1['B'] = hisid
        sig_list = [resp1['rA'],rB,hisid]
        sig_data = bencode(sig_list)
        sig_hash = sha(sig_data).digest()
        sig_asn1 = str(self.my_keypair.sign_dsa_asn1(sig_hash))
        resp1['SA'] = sig_asn1
        return [resp1['rA'],self.create_response1_payload(resp1)]

    def create_response1_payload(self,dict):
        return RESPONSE1+bencode(dict)



    def send(self,data):
        """ send length-prefixed message """
        self.b.send(data)

    def recv(self):
        """ received length-prefixed message """
        return self.b.recv()

    def close(self):
        self.b.close()
        
