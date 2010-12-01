# Written George Milescu
# see LICENSE.txt for license information

# This class contains all util methods related to the ProxyService

import string
import random

def generate_proxy_challenge():
    """ Generates a challenge (8 byte long random number) that a doe sends to a proxy during the handshake
    
    @return: an 8 byte log string
    """
    # Generate a random challenge - random number on 8 bytes (62**8 possible combinations)
    chars = string.letters + string.digits #len(chars)=62
    challenge = ''
    for i in range(8):
        challenge = challenge + random.choice(chars)
    
    return challenge


def decode_challenge_from_peerid(peerid):
    """ Method used to retrieve (decode) a challenge from a peerid
    
    @param peerid: the peerid of the peer whose challenge is to be retrieved
    
    @return: a number, the challenge previously send to that peer, and encoded by the peer in its peerid
    """

    return peerid[12:20]


def encode_challenge_in_peerid(peerid, challenge):
    """ Method used to insert (encode) a challenge into a peerid
    
    @param peerid: the regular peerid, into which the challenge will be encoded
    @param challenge: an 8 byte long number, to be encoded in the peerid
    
    @return: a new peerid, with the challenge encoded in it
    """

    # encoded_peer_id = | regular_peer_id[1:12] | challenge[1:8] |
    encoded_peer_id = peerid[:12] + challenge # len(self.challenge) = 8
    
    return encoded_peer_id 
