import logging
logger = logging.getLogger(__name__)

try:
    from gmpy import mpz, invert, gcd

except ImportError:
    raise RuntimeError("Cannot continue without gmpy")

try:
    from Crypto.Random.random import StrongRandom
    from Crypto.Util.number import long_to_bytes, bytes_to_long, GCD

except ImportError:
    raise RuntimeError("Cannot continue without pycrypto")

try:
    from M2Crypto import EVP, DH
    from M2Crypto.m2 import dec_to_bn, bn_to_mpi, mpi_to_bn, bn_to_hex, bin_to_bn

    def aes_encrypt_str(aes_key, plain_str):
        if isinstance(aes_key, long):
            aes_key = long_to_bytes(aes_key, 16)
        cipher = EVP.Cipher(alg='aes_128_ecb', key=aes_key, iv='\x00' * 16, op=1)
        ret = cipher.update(plain_str)
        return ret + cipher.final()

    def aes_decrypt_str(aes_key, encr_str):
        if isinstance(aes_key, long):
            aes_key = long_to_bytes(aes_key, 16)
        # ATTENTION: If the key has the wrong length M2Crypto will segfault!!!
        if len(aes_key) != 16:
            raise ValueError("aes_encrypt_str: wrong key length: %s for key %s " % (len(aes_key),
                                                                                    aes_key.encode('HEX')))

        cipher = EVP.Cipher(alg='aes_128_ecb', key=aes_key, iv='\x00' * 16, op=0)
        ret = cipher.update(encr_str)
        return ret + cipher.final()

    def mpi_to_dec(mpi):
        bn = mpi_to_bn(mpi)
        hexval = bn_to_hex(bn)
        dec = int(hexval, 16)
        return dec

    def dec_to_mpi(dec):
        bn = dec_to_bn('%s' % dec)
        mpi = bn_to_mpi(bn)
        return mpi

    def bin_to_dec(binval):
        bn = bin_to_bn(binval)
        hexval = bn_to_hex(bn)
        dec = int(hexval, 16)
        return dec

except ImportError as e:
    raise RuntimeError("Cannot continue without M2Crypto" + str(e))
