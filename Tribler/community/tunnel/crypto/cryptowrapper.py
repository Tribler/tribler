import logging
logger = logging.getLogger(__name__)

try:
    from gmpy import mpz, rand, invert, gcd
    rand('init', 128)
    rand('seed')

except ImportError:
    raise RuntimeError("Cannot continue without gmpy")

try:
    from Crypto.Random.random import StrongRandom
    from Crypto.Util.number import long_to_bytes, bytes_to_long, GCD

except ImportError:
    raise RuntimeError("Cannot continue without pycrypto")

try:
    from M2Crypto import EVP

    def aes_encrypt_str(aes_key, plain_str):
        if isinstance(aes_key, long):
            aes_key = long_to_bytes(aes_key, 16)
        cipher = EVP.Cipher(alg='aes_128_ecb', key=aes_key, iv='\x00' * 16, op=1)
        ret = cipher.update(plain_str)
        return ret + cipher.final()

    def aes_decrypt_str(aes_key, encr_str):
        if isinstance(aes_key, long):
            aes_key = long_to_bytes(aes_key, 16)
        cipher = EVP.Cipher(alg='aes_128_ecb', key=aes_key, iv='\x00' * 16, op=0)
        ret = cipher.update(encr_str)
        return ret + cipher.final()

except ImportError as e:
    raise RuntimeError("Cannot continue without M2Crypto" + str(e))

