from Crypto.Random.random import StrongRandom
from Crypto.Util.number import GCD, bytes_to_long, long_to_bytes, inverse
from Crypto.PublicKey import RSA

from gmpy import mpz

from random import randint
from time import time
from Tribler.community.privatesearch.rsa import rsa_init
from collections import namedtuple

PallierKey = namedtuple('PallierKey', ['n', 'n2', 'g', 'lambda_', 'd'])

# using same variable names as implementation by Zeki


def pallier_init(rsa_key):
    n = mpz(rsa_key.n)
    n2 = mpz(pow(n, 2))

    g = mpz(n + 1)

    # LCM from https://github.com/kmcneelyshaw/pycrypto/commit/98c22cc691c1840db380ad04c22169721a946b50
    x = rsa_key.p - 1
    y = rsa_key.q - 1
    if y > x:
        x, y = y, x

    lambda_ = mpz((x / GCD(x, y)) * y)

    d = pow(g, lambda_, n2)
    d = (d - 1) / n
    d = mpz(inverse(d, n))
    return PallierKey(n, n2, g, lambda_, d)


def pallier_encrypt(key, element):
    assert element in [0, 1], element

    _n = long(key.n)
    while True:
        r = StrongRandom().randint(1, _n)
        if GCD(r, _n) == 1:
            break
    r = mpz(r)

    # key_g < n2, so no need for modulo
    t1 = key.g if element else 1
    t2 = pow(r, key.n, key.n2)

    cipher = (t1 * t2) % key.n2
    return long(cipher)


def pallier_decrypt(key, cipher):
    cipher_ = mpz(cipher)

    t1 = pow(cipher_, key.lambda_, key.n2)
    t1 = (t1 - 1) / key.n

    value = (t1 * key.d) % key.n
    return long(value)


def pallier_multiply(cipher, times, n2):
    cipher_ = mpz(cipher)
    times_ = mpz(times)
    n2_ = mpz(n2)
    return long(pow(cipher_, times_, n2_))


def pallier_add(cipher1, cipher2, n2):
    return (cipher1 * cipher2) % n2

if __name__ == "__main__":
    # lets check if this pallier thing works
    key = rsa_init(1024)
    key = pallier_init(key)

    encrypted0 = pallier_encrypt(key, 0)
    encrypted1 = pallier_encrypt(key, 1)

    test = pallier_decrypt(key, 1)
    assert test == 0, test

    test = pallier_decrypt(key, encrypted0)
    assert test == 0, test

    test = pallier_decrypt(key, encrypted1)
    assert test == 1, test

    encrypted2 = pallier_add(encrypted1, encrypted1, key.n2)
    test = pallier_decrypt(key, encrypted2)
    assert test == 2, test

    encrypted4 = pallier_add(encrypted2, encrypted2, key.n2)
    test = pallier_decrypt(key, encrypted4)
    assert test == 4, test

    encrypted1_ = pallier_add(1, encrypted1, key.n2)
    test = pallier_decrypt(key, encrypted1_)
    assert test == 1, test

    encrypted0_ = pallier_multiply(encrypted0, 10, key.n2)
    test = pallier_decrypt(key, encrypted0_)
    assert test == 0, test

    encrypted10 = pallier_multiply(encrypted1, 10, key.n2)
    test = pallier_decrypt(key, encrypted10)
    assert test == 10, test

    # bytes_to_long check
    test = bytes_to_long(long_to_bytes(key.n, 128))
    assert test == key.n, test

    test = pallier_decrypt(key, bytes_to_long(long_to_bytes(encrypted0, 128)))
    assert test == 0, test

    test = pallier_decrypt(key, bytes_to_long(long_to_bytes(encrypted1, 128)))
    assert test == 1, test

    # performance
    t1 = time()
    random_list = [randint(0, 1) for _ in xrange(100)]
    for i, value in enumerate(random_list):
        pallier_encrypt(key, value)
    print time() - t1
