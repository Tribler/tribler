import logging
logger = logging.getLogger(__name__)

try:
    from gmpy import mpz, rand, invert

except ImportError:
    logger.warning('Using fallback for gmpy, not recommended as it hurts performance and is less tested')

    def mpz(a):
        return a

    from random import randint
    def rand(calltype, param):
        if calltype == 'next':
            return randint(0, param)

    def egcd(a, b):
        lastremainder, remainder = abs(a), abs(b)
        x, lastx, y, lasty = 0, 1, 1, 0
        while remainder:
            lastremainder, (quotient, remainder) = remainder, divmod(lastremainder, remainder)
            x, lastx = lastx - quotient * x, x
            y, lasty = lasty - quotient * y, y
        return lastremainder, lastx * (-1 if a < 0 else 1), lasty * (-1 if b < 0 else 1)

    def invert(x, m):
        g, x, y = egcd(x, m)
        if g != 1:
            raise Exception('modular inverse does not exist, "%d"' % g)
        return x % m

try:
    raise ImportError()
    from Crypto.Util.number import long_to_bytes
    from Crypto.Random.random import StrongRandom
    from Crypto.Cipher import AES

    def aes_encrypt_str(aes_key, plain_str):
        cipher = AES.new(long_to_bytes(aes_key, 16), AES.MODE_CFB, '\x00' * 16)
        return cipher.encrypt(plain_str)

    def aes_decrypt_str(aes_key, encr_str):
        cipher = AES.new(long_to_bytes(aes_key, 16), AES.MODE_CFB, '\x00' * 16)
        return cipher.decrypt(encr_str)

except ImportError:
    from random import Random as StrongRandom

    from Tribler.community.privatesemantic.conversion import long_to_bytes
    from M2Crypto import EVP

    def aes_encrypt_str(aes_key, plain_str):
        cipher = EVP.Cipher(alg='aes_128_cfb', key=long_to_bytes(aes_key, 16), iv='\x00' * 16, op=1)
        ret = cipher.update(plain_str)
        return ret + cipher.final()

    def aes_decrypt_str(aes_key, encr_str):
        cipher = EVP.Cipher(alg='aes_128_cfb', key=long_to_bytes(aes_key, 16), iv='\x00' * 16, op=0)
        ret = cipher.update(encr_str)
        return ret + cipher.final()
