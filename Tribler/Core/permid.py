# Written by Arno Bakker
# see LICENSE for license information
import os
import logging
from M2Crypto import Rand, EC, BIO
from Tribler.dispersy.crypto import LibNaCLSK

logger = logging.getLogger(__name__)

# Internal constants
KEYPAIR_ECC_CURVE = EC.NID_sect233k1
NUM_RANDOM_BITS = 1024 * 8  # bits

# Exported functions

# a workaround is needed for Tribler to function on Windows 64 bit
# instead of invoking EC.load_key(filename), we should use the M2Crypto.BIO buffer
# see http://stackoverflow.com/questions/33720087/error-when-importing-m2crypto-in-python-on-windows-x64

def init():
    Rand.rand_seed(os.urandom(NUM_RANDOM_BITS / 8))


def generate_keypair():
    ec_keypair = EC.gen_params(KEYPAIR_ECC_CURVE)
    ec_keypair.gen_key()
    return ec_keypair


def read_keypair(keypairfilename):
    membuf = BIO.MemoryBuffer(open(keypairfilename, 'rb').read())
    key = EC.load_key_bio(membuf)
    membuf.close()
    return key


def save_keypair(keypair, keypairfilename):
    membuf = BIO.MemoryBuffer()
    keypair.save_key_bio(membuf, None)
    with open(keypairfilename, 'w') as file:
        file.write(membuf.read())
    membuf.close()


def save_pub_key(keypair, pubkeyfilename):
    membuf = BIO.MemoryBuffer()
    keypair.save_pub_key_bio(membuf)
    with open(pubkeyfilename, 'w') as file:
        file.write(membuf.read())
    membuf.close()


def generate_keypair_multichain():
    return LibNaCLSK()


def read_keypair_multichain(keypairfilename):
    with open(keypairfilename, 'rb') as keyfile:
        binarykey = keyfile.read()
    return LibNaCLSK(binarykey=binarykey)


def save_keypair_multichain(keypair, keypairfilename):
    with open(keypairfilename, 'wb') as keyfile:
        keyfile.write(keypair.key.sk)
        keyfile.write(keypair.key.seed)

def save_pub_key_multichain(keypair, pubkeyfilename):
    with open(pubkeyfilename, 'wb') as keyfile:
        keyfile.write(keypair.key.pk)

