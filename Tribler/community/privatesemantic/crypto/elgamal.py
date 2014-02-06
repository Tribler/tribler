from time import time
from collections import namedtuple
from random import Random

ElGamalKey = namedtuple('ElGamalKey', ['p', 'g', 'y', 'x', 'size'])

def elgamal_init(bits):
    key = ElGamal.generate(bits, Random.new().read)
    return ElGamalKey(mpz(key.p), mpz(key.g), mpz(key.y), mpz(key.x), bits)

def elgamal_encrypt(key, element):
    assert isinstance(element, (long, int)), type(element)

    _p = long(key.p)
    while 1:
        k = StrongRandom().randint(1, _p - 1)
        if GCD(k, _p - 1) == 1: break

    _element = mpz(element)
    _k = mpz(k)

    c1 = pow(key.g, _k, key.p)
    c2 = (_element * pow(key.y, _k, key.p)) % key.p
    return (long(c1), long(c2))

def elgamal_decrypt(key, cipher):
    ax = pow(cipher[0], key.x, key.p)
    plaintext = (cipher[1] * inverse(ax, long(key.p))) % key.p
    return plaintext

if __name__ == "__main__":
    # lets check if this elgamal thing works

    t1 = time()
    key = elgamal_init(1024)

    t2 = time()
    encrypted3 = elgamal_encrypt(key, 3l)

    t3 = time()
    encrypted2 = elgamal_encrypt(key, 2l)

    t4 = time()
    encrypted6 = (encrypted3[0] * encrypted2[0], encrypted3[1] * encrypted2[1])

    t5 = time()

    print elgamal_decrypt(key, encrypted6)
    print time() - t5, t5 - t4, t4 - t3, t3 - t2, t2 - t1
