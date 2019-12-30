"""
Permanent Identifier.

Author(s): Arno Bakker
"""
import logging

from ipv8.keyvault.private.libnaclkey import LibNaCLSK

logger = logging.getLogger(__name__)


def generate_keypair_trustchain():
    return LibNaCLSK()


def read_keypair_trustchain(keypairfilename):
    with keypairfilename.open(mode='rb') as keyfile:
        binarykey = keyfile.read()
    return LibNaCLSK(binarykey=binarykey)


def save_keypair_trustchain(keypair, keypairfilename):
    with keypairfilename.open(mode='wb') as keyfile:
        keyfile.write(keypair.key.sk)
        keyfile.write(keypair.key.seed)

def save_pub_key_trustchain(keypair, pubkeyfilename):
    with pubkeyfilename.open(mode='wb') as keyfile:
        keyfile.write(keypair.key.pk)
