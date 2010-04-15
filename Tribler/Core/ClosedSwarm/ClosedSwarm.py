# Written by Njaal Borch
# see LICENSE.txt for license information

import time
import os.path

from base64 import encodestring, decodestring
from M2Crypto.EC import pub_key_from_der

from Tribler.Core.Overlay import permid
from Tribler.Core.BitTornado.bencode import bencode, bdecode

from Tribler.Core.BitTornado.BT1.MessageID import *


# Constants to be put into BaseLib.Core.BitTornado.BT1.MessageID.py
# Also update all the protocol stuff there (flag the extension)


# Parent exception - all exceptions thrown by the ClosedSwarm class
# are children of this class
class ClosedSwarmException(Exception):
    """
    Base class for closed swarm related exceptions
    """
    pass

# Specialized exceptions
class MissingKeyException(ClosedSwarmException):
    """
    No key was available for the operation
    """
    pass

class MissingCertificateException(ClosedSwarmException):
    """
    A required certificate was not found
    """
    pass

class BadMessageException(ClosedSwarmException):
    """
    A bad closed swarm message was received
    """
    pass

class WrongSwarmException(ClosedSwarmException):
    """
    The wrong swarm was specified
    """
    pass

class InvalidSignatureException(ClosedSwarmException):
    """
    Invalid signature
    """
    pass

class InvalidPOAException(ClosedSwarmException):
    """
    The Proof-of-Access was invalid
    """
    pass

class POAExpiredException(ClosedSwarmException):
    """
    The Proof-of-Access has timed out
    """
    pass
    
# Some helper functions

def pubkey_from_der(der_key):
    """
    Return a public key object from a DER encoded key
    """
    return pub_key_from_der(decodestring(der_key))

def generate_cs_keypair(keypair_filename=None, pubkey_filename=None):
    """
    Generate a keypair suitable for a Closed Swarm
    
    Saves to the given files if specified, returns keypair, pubkey
    """
    keypair = permid.generate_keypair()
    if keypair_filename:
        permid.save_keypair(keypair, keypair_filename)

    pubkey = encodestring(str(keypair.pub().get_der())).replace("\n","")
    if pubkey_filename:
        permid.save_pub_key(keypair, pubkey_filename)
    
    return keypair, pubkey

def read_cs_keypair(keypair_filename):
    """
    Read and return a CS keypair from a file
    """
    return permid.read_keypair(keypair_filename)


def read_cs_pubkey(pubkey_filename):
    """
    Read and return the public key of a torrent from a file
    """
    return open(pubkey_filename,"r").read()

def write_poa_to_file(filename, poa):
    """
    Dump the POA to the given file in serialized form
    """
    target = open(filename,"wb")
    target.write(poa.serialize())
    return filename

def read_poa_from_file(filename):
    """
    Read and return a POA object from a file. Throws exception if
    the file was not found or the POA could not be deserialized
    """
    if not os.path.exists(filename):
        raise Exception("File '%s' not found"%filename)
    
    data = open(filename,"rb").read()
    return POA.deserialize(data)

# Some POA helpers
def trivial_get_poa(path, perm_id, swarm_id):
    """
    Look for a POA file for the given permid,swarm_id
    """
    filename = encodestring(perm_id).replace("\n","")
    filename = filename.replace("/","")
    filename = filename.replace("\\","")

    t_id  = encodestring(swarm_id).replace("\n","")
    t_id = t_id.replace("/","")
    t_id = t_id.replace("/","")

    poa_path = os.path.join(path, filename + "." + t_id + ".poa")

    return read_poa_from_file(poa_path)
        
def trivial_save_poa(path, perm_id, swarm_id, poa):
    """
    Save POA
    """
    filename = encodestring(perm_id).replace("\n","")
    filename = filename.replace("/","")
    filename = filename.replace("\\","")

    t_id  = encodestring(swarm_id).replace("\n","")
    t_id = t_id.replace("/","")
    t_id = t_id.replace("/","")

    # if the path does not exist, try to create it
    if not os.path.exists(path):
        os.makedirs(path)

    poa_path = os.path.join(path, filename + "." + t_id + ".poa")
    
    return write_poa_to_file(poa_path, poa)


class POA:
    """
    Proof of access wrapper
    """
    
    def __init__(self, torrent_id, torrent_pub_key, node_pub_key,
                 signature="", expire_time=0):
        """
        Create a new POA for this torrent
        """
        self.torrent_id = torrent_id
        self.torrent_pub_key = torrent_pub_key
        self.node_pub_key = node_pub_key
        self.signature = signature
        self.expire_time = expire_time

    def serialize_to_list(self):
        """
        Serialize to a list of entries
        """
        return [self.torrent_id,
                self.torrent_pub_key,
                self.node_pub_key,
                self.expire_time,
                self.signature]
        
    def deserialize_from_list(lst):
        """
        Deserialize a POA from a list of elements.

        The POA object should be verified after deserializing
        """
        if not lst or len(lst) < 5:
            raise InvalidPOAException("Bad list")

        torrent_id = lst[0]
        torrent_pub_key = lst[1]
        node_pub_key = lst[2]
        expire_time = lst[3]
        signature = lst[4]
        return POA(torrent_id, torrent_pub_key,
                   node_pub_key, signature, expire_time)

    deserialize_from_list = staticmethod(deserialize_from_list)
    
    def serialize(self):
        """
        Return a bencoded, serialized POA
        """
        lst = [self.torrent_id,
               self.torrent_pub_key,
               self.node_pub_key,
               self.expire_time,
               self.signature]
        return bencode(lst)

    def deserialize(encoded):
        """
        De-serialize a serialized POA. Returns a POA object, or raises
        InvalidPOAException if the POA was bad
        """
        if not encoded:
            raise InvalidPOAException("Cannot deserialize nothing")
        
        try:
            lst = bdecode(encoded)
            if len(lst) < 5:
                raise InvalidPOAException("Too few entries (got %d, "
                                          "expected 5)"%len(lst))
            return POA(lst[0], lst[1],
                       lst[2], expire_time=lst[3], signature=lst[4])
        except Exception, e:
            raise InvalidPOAException("De-serialization failed (%s)"%e)


    deserialize = staticmethod(deserialize)

        
    def get_torrent_pub_key(self):
        """
        Return the base64 encoded torrent pub key for this POA
        """
        return encodestring(self.torrent_pub_key).replace("\n","")
        
    def verify(self):
        """
        Throws an exception if the POA does not hold or has expired
        """

        if self.expire_time and \
               self.expire_time < time.mktime(time.gmtime()):
            raise POAExpiredException()
        
        try:
            lst = [self.torrent_id, 
                   self.torrent_pub_key, 
                   self.node_pub_key]
            b_list = bencode(lst)
            digest = permid.sha(b_list).digest()
            pub = pub_key_from_der(self.torrent_pub_key)
            if not pub.verify_dsa_asn1(digest, self.signature):
                raise InvalidPOAException("Proof of access verification failed")
        except Exception, e:
            raise InvalidPOAException("Bad POA: %s"%e)
        
    def sign(self, torrent_key_pair):
        """
        Sign the POA
        """
        
        lst = [self.torrent_id, 
                self.torrent_pub_key, 
                self.node_pub_key]
        b_list = bencode(lst)
        digest = permid.sha(b_list).digest()

        self.signature = torrent_key_pair.sign_dsa_asn1(digest)

    def save(self, filename):
        target = open(filename,"wb")
        target.write(self.serialize())
        target.close()
        return filename

    def load(filename):
        """
        Read and return a POA object from a file. Throws exception if
        the file was not found or the POA could not be deserialized
        """
        if not os.path.exists(filename):
            raise Exception("File '%s' not found"%filename)
    
        data = open(filename,"rb").read()
        return POA.deserialize(data)

    load = staticmethod(load)

        
        
def create_poa(torrent_id, torrent_keypair, pub_permid, expire_time=0):
    """
    Create and return a certificate 'proof of access' to the given node.
    Notice that this function reuire the full keypair of the torrent
    """
    poa = POA(torrent_id, 
              str(torrent_keypair.pub().get_der()),
              pub_permid,
              expire_time=expire_time)
    poa.sign(torrent_keypair)
    return poa



class ClosedSwarm:
    """
    This is a class that can authenticate two peers to participate in
    a closed swarm.
    The certificate given must be the "proof of access" to the torrent
    in question

    How to use:
    For the initiator:
    cs = ClosedSwarm(my_keypair, torrent_id, torrent_pubkey, poa)

    node a (initiator)                | node b
    msg1 = cs_a.a_create_challenge()  |  
    send(msg1)                        | msg1 = recv()
                                      | msg2 = cs.b_create_challenge(msg1)
    msg2 = recv()                     | send(msg2)
    msg3 = cs.a_provide_poa_message(msg2)|
    send(msg3)                        | msg3 = recv()
                                      | msg4 = b_provide_poa_message(msg3)
    msg4 = recv()                     | send(msg4)
    cs.a_check_poa_message(msg4)      |
    if cs.is_remote_node_authorized():| if cs.is_remote_node_authorized():
    ...

    The protocol is allowed to stop after msg3, which means that node b
    will not be authorized. This will happen if node b is seeding, or is
    not authorized.
    
    If something bad happens (bad messages, invalid signatures or keys etc),
    exceptions are thrown.
    
    All exceptions thrown are children of ClosedSwarmException
        
    """
    IDLE = 0
    EXPECTING_RETURN_CHALLENGE = 1   # A sent challenge to B, expects challenge
    EXPECTING_INITIATOR_RESPONSE = 2 # B sent challenge to A, expects POA
    SEND_INITIATOR_RESPONSE = 3      # A sent POA to B, expects POA
    COMPLETED = 4                    # Nothing more expected
    
    def __init__(self, my_keypair, 
                 torrent_id, torrent_pubkeys,
                 poa): 

        if poa:
            if not poa.__class__ == POA:
                raise Exception("POA is not of class POA, but of class %s"%poa.__class__)
            
        assert torrent_pubkeys.__class__ == list

        self.state = self.IDLE

        self.my_keypair = my_keypair
        self.pub_permid = str(my_keypair.pub().get_der())

        self.torrent_id = torrent_id
        self.torrent_pubkeys = torrent_pubkeys
        self.poa = poa
        self.remote_node_authorized = False

        self.nonce_a = None
        self.nonce_b = None
        self.remote_nonce = None # Shortcut
        self.my_nonce = None # Shortcut
        
        if self.poa: # Allow nodes to support CS but not have a POA (e.g. if they are seeding)
            if self.poa.get_torrent_pub_key() not in self.torrent_pubkeys:
                import sys
                print >> sys.stderr, "Bad POA for this torrent (wrong torrent key!)"
                self.poa = None
                
    def is_remote_node_authorized(self):
        """
        Returns True iff the remote node is authorized to receive traffic
        """
        return self.remote_node_authorized

    def set_poa(self, poa):
        """
        Set the POA of the closed swarm run
        """
        assert poa.__class__ == POA
        self.poa = poa
        
    def give_up(self):
        """
        Give up the protocol - set to completed
        """
        self.state = self.COMPLETED
        
    def is_incomplete(self):
        """
        Not completed the CS exchange yet
        """
        return self.state != self.COMPLETED

    def _create_challenge_msg(self, msg_id):
        """
        Create the first message (from both nodes)
        """
        [self.my_nonce, my_nonce_bencoded] = permid.generate_challenge()
        # Serialize this message
        return [msg_id,
                self.torrent_id,
                self.my_nonce]
        

    def a_create_challenge(self): 
        """
        1st message
        Initiate a challenge, returns a list
        """
        assert self.state == self.IDLE
        self.state = self.EXPECTING_RETURN_CHALLENGE
        return self._create_challenge_msg(CS_CHALLENGE_A)

    def b_create_challenge(self, lst):
        """
        2nd message
        Return a message that can be sent in reply to the given challenge.
        Throws exception on bad message or if this cannot be done
        BadMessageException - Message was bad
        MissingKeyException - Don't have the necessary keys
        MissingCertificateException - Don't have a certificate
        """
        assert self.state == self.IDLE
        self.state = self.EXPECTING_INITIATOR_RESPONSE

        # List should be [INITIAL_CHALLENGE, torrent_id, nonce]
        if len(lst) != 3:
            raise BadMessageException("Bad number of elements in message, expected 2, got %d"%len(lst))
        if lst[0] != CS_CHALLENGE_A:
            raise BadMessageException("Expected initial challenge, got something else")
        [torrent_id, nonce_a] = lst[1:]

        # Now we generate the response
        if self.torrent_id != torrent_id:
            raise WrongSwarmException("Expected %s, got %s"%(self.torrent_id,
                                                             torrent_id))

        # Save the remote nonce too
        self.remote_nonce = nonce_a
        
        # We got a correct challenge for the correct torrent, make our message
        return self._create_challenge_msg(CS_CHALLENGE_B)

    def _create_poa_message(self, msg_id, nonce_a, nonce_b):
        """
        Create the POA exchange message (messages 3 and 4).
        """
        assert msg_id
        assert nonce_a
        assert nonce_b
        assert self.poa
        
        # Provide the certificate 
        if not self.poa:
            raise MissingCertificateException()

        msg = [msg_id] + self.poa.serialize_to_list()

        # Add signature
        lst = [nonce_a,
               nonce_b,
               self.poa.serialize()]
        
        b_list = bencode(lst)
        digest = permid.sha(b_list).digest()
        sig = self.my_keypair.sign_dsa_asn1(digest)
        msg.append(sig)

        return msg

    def _validate_poa_message(self, lst, nonce_a, nonce_b):
        """
        Validate an incoming POA message - throw exception if bad.
        Returns the POA if successful
        """
        assert nonce_a
        assert nonce_b
        
        if len(lst) != 7:
            raise BadMessageException("Require 7 elements, got %d"%len(lst))
        
        poa = POA.deserialize_from_list(lst[1:-1])
        sig = lst[-1]
        assert poa.node_pub_key
        
        if poa.torrent_id != self.torrent_id:
            raise WrongSwarmException()

        if poa.get_torrent_pub_key() not in self.torrent_pubkeys:
            raise InvalidPOAException("Bad POA for this torrent")

        # Check the signature
        lst = [nonce_a,
               nonce_b,
               poa.serialize()]
        import sys
        b_list = bencode(lst)
        digest = permid.sha(b_list).digest()
        try:
            pub = pub_key_from_der(poa.node_pub_key)
        except:
            print >> sys.stderr, "The node_pub_key is no good"
            print >> sys.stderr, poa.node_pub_key
            raise Exception("JIKES!")
            
        if not pub.verify_dsa_asn1(digest, sig):
            raise InvalidSignatureException("Freshness test failed")
            
        # Passed the freshness test, now check the certificate
        poa.verify() # Throws exception if bad
        return poa

    
    def a_provide_poa_message(self, lst):
        """
        3rd message
        Got a reply to an initial challenge.  Returns
        the challenge sent by the remote node
        """
        assert self.state == self.EXPECTING_RETURN_CHALLENGE
        self.state = self.SEND_INITIATOR_RESPONSE
        if len(lst) != 3:
            raise BadMessageException("Require 3 elements, got %d"%\
                                     len(lst))
        if lst[0] != CS_CHALLENGE_B:
            raise BadMessageException("Expected RETURN_CHALLENGE, got '%s'"%lst[0])
        if lst[1] != self.torrent_id:
            raise WrongSwarmException()

        self.remote_nonce = lst[2]
        msg = self._create_poa_message(CS_POA_EXCHANGE_A, self.my_nonce, self.remote_nonce)
        return msg
            

    def b_provide_poa_message(self, lst, i_am_seeding=False):
        """
        4rd message
        Got a reply to an initial challenge.  Returns
        the challenge sent by the remote node or None if i_am_seeding is true
        """
        assert self.state == self.EXPECTING_INITIATOR_RESPONSE
        self.state = self.COMPLETED

        if lst[0] != CS_POA_EXCHANGE_A:
            import sys
            print >> sys.stderr, "Not CS_POA_EXCHANGE_A"
            raise BadMessageException("Expected POA EXCHANGE")

        try:
            self._validate_poa_message(lst, self.remote_nonce,
                                       self.my_nonce)
            self.remote_node_authorized = True
        except Exception, e:
            self.remote_node_authorized = False
            import sys
            print >> sys.stderr, "POA could not be validated:",e
            #raise e // The remote node failed, but we can still make it!

        if i_am_seeding:
            return None
        
        msg = self._create_poa_message(CS_POA_EXCHANGE_B, self.remote_nonce, self.my_nonce)
        return msg

    def a_check_poa_message(self, lst):
        """
        Verify receiption of 4th message
        """
        assert self.state == self.SEND_INITIATOR_RESPONSE
        self.state = self.COMPLETED

        if lst[0] != CS_POA_EXCHANGE_B:
            raise BadMessageException("Expected POA EXCHANGE")

        self._validate_poa_message(lst, self.my_nonce, self.remote_nonce)

        # Remote node authorized!
        self.remote_node_authorized = True

