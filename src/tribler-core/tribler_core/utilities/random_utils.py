import random
import string


def random_string(size=6, chars=string.ascii_uppercase + string.digits):
    """ Generates a random string """
    return ''.join(random.choice(chars) for _ in range(size))


def random_infohash(random_gen=None):
    r = random_gen or random
    """ Generates a random torrent infohash binary string """
    return r.getrandbits(20 * 8).to_bytes(20, byteorder='big')
