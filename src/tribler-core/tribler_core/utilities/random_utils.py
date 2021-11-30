import random


def random_infohash(random_gen=None):
    r = random_gen or random
    """ Generates a random torrent infohash binary string """
    return r.getrandbits(20 * 8).to_bytes(20, byteorder='big')
