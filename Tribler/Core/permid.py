# Written by Arno Bakker
# see LICENSE.txt for license information
from copy import deepcopy
import os
import logging
from M2Crypto import Rand, EC

from Tribler.Core.Utilities.Crypto import sha
from Tribler.Core.Utilities.bencode import bencode

logger = logging.getLogger(__name__)

# Internal constants
KEYPAIR_ECC_CURVE = EC.NID_sect233k1
NUM_RANDOM_BITS = 1024 * 8  # bits

# Exported functions


def init():
    Rand.rand_seed(os.urandom(NUM_RANDOM_BITS / 8))


def generate_keypair():
    ec_keypair = EC.gen_params(KEYPAIR_ECC_CURVE)
    ec_keypair.gen_key()
    return ec_keypair


def read_keypair(keypairfilename):
    return EC.load_key(keypairfilename)


def save_keypair(keypair, keypairfilename):
    keypair.save_key(keypairfilename, None)


def save_pub_key(keypair, pubkeyfilename):
    keypair.save_pub_key(pubkeyfilename)


# Internal functions

#
# The following methods and ChallengeResponse class implement a
# Challenge/Response identification protocol, notably the
# ISO/IEC 9798-3 protocol, as described in $10.3.3 (ii) (2) of the
# ``Handbook of Applied Cryptography''by  Alfred J. Menezes et al.
#


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
        logger.error("permid: Exception in verify_torrent_signature: %s", str(e))
        return False
