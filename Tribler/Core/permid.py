# Written by Arno Bakker
# see LICENSE.txt for license information
import os
import logging
from M2Crypto import Rand, EC

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
