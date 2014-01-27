# Written by Niels Zeilemaker

from Crypto.Random.random import StrongRandom
from Crypto.Util.number import GCD, bytes_to_long, long_to_bytes, inverse
from Crypto.Cipher import AES

from gmpy import mpz, invert, rand

from random import randint, Random, choice
from time import time
from hashlib import md5
from sys import maxint

from rsa import rsa_init
from collections import namedtuple
from polycreate import compute_coeff
from itertools import groupby
from cProfile import Profile
from string import ascii_uppercase, digits

PaillierKey = namedtuple('PaillierKey', ['n', 'n2', 'g', 'lambda_', 'd', 'size', 'encsize'])

# using same variable names as implementation by Zeki
def improved_pow(base, exponent, modulo):
    if exponent == 1:
        return base

    if exponent > 1:
        return pow(base, exponent, modulo)

    d = invert(base, modulo)
    return pow(d, -exponent, modulo)

def paillier_init(rsa_key):
    rand('init', 128)
    rand('seed', StrongRandom().randint(0, maxint))

    n = mpz(rsa_key.n)
    n2 = mpz(n ** 2)

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
    return PaillierKey(n, n2, g, lambda_, d, rsa_key.size, rsa_key.size * 2)

def paillier_encrypt(key, element):
    assert isinstance(element, (int, long)), type(element)

    _n = long(key.n)
    while True:
        r = rand('next', _n)
        if GCD(r, _n) == 1: break
    r = mpz(r)

    t1 = improved_pow(key.g, element, key.n2)
    t2 = pow(r, key.n, key.n2)
    cipher = (t1 * t2) % key.n2
    return long(cipher)

def paillier_decrypt(key, cipher):
    cipher_ = mpz(cipher)

    t1 = pow(cipher_, key.lambda_, key.n2)
    t1 = (t1 - 1) / key.n

    value = (t1 * key.d) % key.n
    return long(value)

def paillier_decrypt_str(key, cipher):
    assert isinstance(cipher, str), type(cipher)
    return

def paillier_multiply(cipher, times, n2):
    cipher_ = mpz(cipher)
    times_ = mpz(times)
    n2_ = mpz(n2)
    return long(pow(cipher_, times_, n2_))

def paillier_add(cipher1, cipher2, n2):
    return (cipher1 * cipher2) % n2

def paillier_add_unenc(cipher, value, g, n2):
    return cipher * improved_pow(g, value, n2)

def paillier_polyval(coefficients, x, n2):
    result = coefficients[0]
    for coefficient in coefficients[1:]:
        result = paillier_add(paillier_multiply(result, x, n2), coefficient, n2)

    return result

def encrypt_str(key, plain_str):
    aes_key = StrongRandom().getrandbits(128)
    cipher = AES.new(long_to_bytes(aes_key, 16), AES.MODE_CFB, '\x00' * 16)

    enc_str = cipher.encrypt(plain_str)
    enc_aes_key = long_to_bytes(paillier_encrypt(key, aes_key), key.encsize / 8)
    return enc_aes_key + enc_str

def decrypt_str(key, encr_str):
    enc_aes_key = bytes_to_long(encr_str[:key.encsize / 8])
    aes_key = paillier_decrypt(key, enc_aes_key)

    cipher = AES.new(long_to_bytes(aes_key, 16), AES.MODE_CFB, '\x00' * 16)
    plain_str = cipher.decrypt(encr_str[key.encsize / 8:])
    return plain_str

if __name__ == "__main__":
    # lets check if this paillier thing works
    key = rsa_init(1024)
    key = paillier_init(key)

    assert bytes_to_long(long_to_bytes(key.g, 128)) == key.g

    r = Random()
    set1 = [r.randint(0, 2 ** 40) for i in range(100)]
    set2 = [r.randint(0, 2 ** 40) for i in range(100)]
    should_overlap = set2[0] = set1[0]  # force overlap

    # create partitions
    # convert our infohashes to 40 bit long
    bitmask = (2 ** 40) - 1
    set1 = [long(md5(str(infohash)).hexdigest(), 16) & bitmask for infohash in set1]
    set2 = [long(md5(str(infohash)).hexdigest(), 16) & bitmask for infohash in set2]

    assert all(val < bitmask for val in set1)
    assert all(val < bitmask for val in set2)

    # partition the infohashes
    partitionmask = (2 ** 32) - 1
    set1 = [(val >> 32, val & partitionmask) for val in set1]
    set2 = [(val >> 32, val & partitionmask) for val in set2]

    set1.sort()
    set2.sort()

    a_results = {}
    for partition, g in groupby(set1, lambda x: x[0]):
        assert 0 <= partition <= 255, partition

        values = [value for _, value in list(g)]
        coeffs = compute_coeff(values)
        coeffs = [paillier_encrypt(key, coeff) for coeff in coeffs]

        a_results[partition] = coeffs

    b_results = []
    for partition, g in groupby(set2, lambda x: x[0]):
        assert partition <= 255, partition
        assert partition >= 0, partition

        if partition in a_results:
            values = [value for _, value in list(g)]
            for val in values:
                py = paillier_polyval(a_results[partition], val, key.n2)
                py = paillier_multiply(py, randint(0, 2 ** 40), key.n2)
                py = paillier_add_unenc(py, val, key.g, key.n2)
                b_results.append((py, val))

    for b_result, b_val in b_results:
        if should_overlap == b_val:
            assert paillier_decrypt(key, b_result) == b_val

    encrypted1 = paillier_encrypt(key, 1l)
    _encrypted0 = paillier_add_unenc(encrypted1, -1, key.g, key.n2)
    assert 0l == paillier_decrypt(key, _encrypted0)

    encrypted0 = paillier_encrypt(key, 0l)
    encrypted1 = paillier_encrypt(key, 1l)

    test = paillier_decrypt(key, 1l)
    assert test == 0l, test

    test = paillier_decrypt(key, encrypted0)
    assert test == 0l, test

    test = paillier_decrypt(key, encrypted1)
    assert test == 1l, test

    encrypted2 = paillier_add(encrypted1, encrypted1, key.n2)
    test = paillier_decrypt(key, encrypted2)
    assert test == 2l, test

    encrypted4 = paillier_add(encrypted2, encrypted2, key.n2)
    test = paillier_decrypt(key, encrypted4)
    assert test == 4l, test

    encrypted1_ = paillier_add(1, encrypted1, key.n2)
    test = paillier_decrypt(key, encrypted1_)
    assert test == 1l, test

    encrypted0_ = paillier_multiply(encrypted0, 10, key.n2)
    test = paillier_decrypt(key, encrypted0_)
    assert test == 0l, test

    encrypted10 = paillier_multiply(encrypted1, 10, key.n2)
    test = paillier_decrypt(key, encrypted10)
    assert test == 10l, test

    # bytes_to_long check
    test = bytes_to_long(long_to_bytes(key.n, 128))
    assert test == key.n, test

    test = paillier_decrypt(key, bytes_to_long(long_to_bytes(encrypted0, 128)))
    assert test == 0l, test

    test = paillier_decrypt(key, bytes_to_long(long_to_bytes(encrypted1, 128)))
    assert test == 1l, test

    random_large_string = ''.join(choice(ascii_uppercase + digits) for _ in range(100001))
    encrypted_str = encrypt_str(key, random_large_string)
    assert random_large_string == decrypt_str(key, encrypted_str)

    def do_perf():
        # performance
        t1 = time()
        random_list = [randint(0, 1) for _ in xrange(1000)]

        t2 = time()
        encrypted_values = []
        for i, value in enumerate(random_list):
            encrypted_values.append(paillier_encrypt(key, value))

        t3 = time()
        for cipher in encrypted_values:
            paillier_decrypt(key, cipher)

        print "Took %.2fs to encrypt %d values, %.2fs to decrypt them (%.2fs to generate the points)" % (t3 - t2, len(random_list), time() - t3, t2 - t1)

    profiler = Profile()
    profiler.runcall(do_perf)
    profiler.print_stats()
