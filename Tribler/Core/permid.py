# Written by Arno Bakker
# see LICENSE.txt for license information

import sys
from Tribler.Core.Utilities.Crypto import sha
from base64 import encodestring
from copy import deepcopy
import traceback
import os
import logging

from M2Crypto import Rand, EC
from Tribler.Core.Utilities.bencode import bencode, bdecode

logger = logging.getLogger(__name__)

# Internal constants
keypair_ecc_curve = EC.NID_sect233k1
num_random_bits = 1024 * 8  # bits

# Protocol states
STATE_INITIAL = 0
STATE_AWAIT_R1 = 1
STATE_AWAIT_R2 = 2
STATE_AUTHENTICATED = 3
STATE_FAILED = 4

# Exported functions


def init():
    Rand.rand_seed(os.urandom(num_random_bits / 8))


def exit():
    pass


def generate_keypair():
    ec_keypair = EC.gen_params(keypair_ecc_curve)
    ec_keypair.gen_key()
    return ec_keypair


def read_keypair(keypairfilename):
    return EC.load_key(keypairfilename)


def read_pub_key(pubfilename):
    return EC.load_pub_key(pubfilename)


def save_keypair(keypair, keypairfilename):
    keypair.save_key(keypairfilename, None)


def save_pub_key(keypair, pubkeyfilename):
    keypair.save_pub_key(pubkeyfilename)


# def show_permid(permid):
# See Tribler/utilities.py

def permid_for_user(permid):
    # Full BASE64-encoded
    return encodestring(permid).replace("\n", "")

# For convenience


def sign_data(plaintext, ec_keypair):
    digest = sha(plaintext).digest()
    return ec_keypair.sign_dsa_asn1(digest)


def verify_data(plaintext, permid, blob):
    pubkey = EC.pub_key_from_der(permid)
    digest = sha(plaintext).digest()
    return pubkey.verify_dsa_asn1(digest, blob)


def verify_data_pubkeyobj(plaintext, pubkey, blob):
    digest = sha(plaintext).digest()
    return pubkey.verify_dsa_asn1(digest, blob)


# Internal functions

#
# The following methods and ChallengeResponse class implement a
# Challenge/Response identification protocol, notably the
# ISO/IEC 9798-3 protocol, as described in $10.3.3 (ii) (2) of the
# ``Handbook of Applied Cryptography''by  Alfred J. Menezes et al.
#

def generate_challenge():
    randomB = Rand.rand_bytes(num_random_bits / 8)
    return [randomB, bencode(randomB)]


def check_challenge(cdata):
    try:
        randomB = bdecode(cdata)
    except:
        return None
    if len(randomB) != num_random_bits / 8:
        return None
    else:
        return randomB


def generate_response1(randomB, peeridB, keypairA):
    randomA = Rand.rand_bytes(num_random_bits / 8)
    response1 = {}
    response1['certA'] = str(keypairA.pub().get_der())
    response1['rA'] = randomA
    response1['B'] = peeridB
    response1['SA'] = sign_response(randomA, randomB, peeridB, keypairA)
    return [randomA, bencode(response1)]


def check_response1(rdata1, randomB, peeridB):
    try:
        response1 = bdecode(rdata1)
    except:
        return [None, None]
    if response1['B'] != peeridB:
        return [None, None]
    pubA_der = response1['certA']
    pubA = EC.pub_key_from_der(pubA_der)
    sigA = response1['SA']
    randomA = response1['rA']
    if verify_response(randomA, randomB, peeridB, pubA, sigA):
        return [randomA, pubA]
    else:
        return [None, None]


def generate_response2(randomA, peeridA, randomB, keypairB):
    response2 = {}
    response2['certB'] = str(keypairB.pub().get_der())
    response2['A'] = peeridA
    response2['SB'] = sign_response(randomB, randomA, peeridA, keypairB)
    return bencode(response2)


def check_response2(rdata2, randomA, peeridA, randomB, peeridB):
    try:
        response2 = bdecode(rdata2)
    except:
        return None
    if response2['A'] != peeridA:
        return None
    pubB_der = response2['certB']
    pubB = EC.pub_key_from_der(pubB_der)
    sigB = response2['SB']
    if verify_response(randomB, randomA, peeridA, pubB, sigB):
        return pubB
    else:
        return None


def sign_response(randomA, randomB, peeridB, keypairA):
    list = [randomA, randomB, peeridB]
    blist = bencode(list)
    digest = sha(blist).digest()
    blob = keypairA.sign_dsa_asn1(digest)
    return blob


def verify_response(randomA, randomB, peeridB, pubA, sigA):
    list = [randomA, randomB, peeridB]
    blist = bencode(list)
    digest = sha(blist).digest()
    return pubA.verify_dsa_asn1(digest, sigA)


# External functions

def create_torrent_signature(metainfo, keypairfilename):
    keypair = EC.load_key(keypairfilename)
    bmetainfo = bencode(metainfo)
    digester = sha(bmetainfo[:])
    digest = digester.digest()
    sigstr = keypair.sign_dsa_asn1(digest)
    metainfo['signature'] = sigstr
    metainfo['signer'] = str(keypair.pub().get_der())


def verify_torrent_signature(metainfo):
    r = deepcopy(metainfo)
    signature = r['signature']
    signer = r['signer']
    del r['signature']
    del r['signer']
    bmetainfo = bencode(r)
    digester = sha(bmetainfo[:])
    digest = digester.digest()
    return do_verify_torrent_signature(digest, signature, signer)


# Internal

def do_verify_torrent_signature(digest, sigstr, permid):
    if permid is None:
        return False
    try:
        ecpub = EC.pub_key_from_der(permid)
        if ecpub is None:
            return False
        intret = ecpub.verify_dsa_asn1(digest, sigstr)
        return intret == 1
    except Exception as e:
        logger.error("permid: Exception in verify_torrent_signature: %s" % str(e))
        return False


# Exported classes
class PermIDException(Exception):
    pass

if __name__ == '__main__':
    init()
