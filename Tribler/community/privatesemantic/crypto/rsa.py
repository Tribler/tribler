# Written by Niels Zeilemaker

from aes import encrypt_str as aes_encrypt_str, decrypt_str as aes_decrypt_str
from ogmpy import mpz, StrongRandom

from Crypto.PublicKey import RSA
from Crypto.Util.number import GCD, bytes_to_long, long_to_bytes

from string import ascii_uppercase, digits
from hashlib import sha1

from time import time
from random import randint, choice
from collections import namedtuple
from sys import maxint
import json

RSAKey = namedtuple('RSAKey', ['n', 'e', 'p', 'q', 'd', 'size', 'encsize'])

def rsa_init(bits=1024):
    key = RSA.generate(bits)
    return RSAKey(mpz(key.key.n), mpz(key.key.e), mpz(key.key.p), mpz(key.key.q), mpz(key.key.d), bits, bits)

def rsa_compatible(n, phi):
    phi = long(phi)
    while True:
        e = StrongRandom().randint(1, phi - 1)
        if GCD(e, phi) == 1: break
    return RSAKey(mpz(n), mpz(e), None, None, None, 1024, 1024)

def rsa_encrypt(key, element):
    assert isinstance(element, (long, int)), type(element)

    _element = mpz(element)
    return long(pow(_element, key.e, key.n))

def rsa_decrypt(key, cipher):
    assert isinstance(cipher, long), type(cipher)

    _cipher = mpz(cipher)
    return long(pow(_cipher, key.d, key.n))

def rsa_sign(key, message):
    message_hash = long(sha1(str(message)).hexdigest(), 16)
    _message_hash = mpz(message_hash)
    return long(pow(_message_hash, key.d, key.n))

def rsa_verify(key, message, signature):
    message_hash = long(sha1(str(message)).hexdigest(), 16)

    _signature = mpz(signature)
    should_be_hash = long(pow(_signature, key.e, key.n))
    return message_hash == should_be_hash

def encrypt_str(key, plain_str):
    aes_key = StrongRandom().getrandbits(128)
    enc_str = aes_encrypt_str(aes_key, plain_str)
    enc_aes_key = long_to_bytes(rsa_encrypt(key, aes_key), key.encsize / 8)
    return enc_aes_key + enc_str

def decrypt_str(key, encr_str):
    enc_aes_key = bytes_to_long(encr_str[:key.encsize / 8])
    aes_key = rsa_decrypt(key, enc_aes_key)
    plain_str = aes_decrypt_str(aes_key, encr_str[key.encsize / 8:])
    return plain_str

def hash_element(element):
    return sha1(str(element)).digest()

def get_bits(number):
    bits = 0
    while number > 2 ** bits:
        bits += 1
    return bits

def key_to_bytes(key):
    non_mpzdict = {}
    for i, prop in enumerate(['n', 'e', 'p', 'q', 'd', 'size']):
        if key[i]:
            non_mpzdict[prop] = long(key[i])

    return json.dumps(non_mpzdict)

def bytes_to_key(bytes):
    keydict = json.loads(bytes)
    return RSAKey(mpz(keydict['n']), mpz(keydict['e']), mpz(keydict['p']) if 'p' in keydict else None, mpz(keydict['q'])  if 'q' in keydict else None, mpz(keydict['d'])  if 'd' in keydict else None, keydict['size'], keydict['size'])

if __name__ == "__main__":
    MAXLONG128 = (1 << 1024) - 1

    # lets check if this rsa thing works
    key = rsa_init(1024)
    serialized_key = bytes_to_key(key_to_bytes(key))

    assert key.n == serialized_key.n, (key.n, serialized_key.n)
    assert key.e == serialized_key.e, (key.e, serialized_key.e)
    assert key.p == serialized_key.p, (key.p, serialized_key.p)
    assert key.q == serialized_key.q, (key.q, serialized_key.q)
    assert key.d == serialized_key.d, (key.d, serialized_key.d)
    assert key.size == serialized_key.size

    encrypted0 = rsa_encrypt(key, 0l)
    encrypted1 = rsa_encrypt(key, 1l)
    assert encrypted0 < MAXLONG128
    assert encrypted1 < MAXLONG128

    test = rsa_decrypt(key, encrypted0)
    assert test == 0l, test

    test = rsa_decrypt(key, encrypted1)
    assert test == 1l, test

    comp_key = rsa_compatible(key.n, key.n / 2)
    compencrypted0 = rsa_encrypt(comp_key, 0l)
    compencrypted1 = rsa_encrypt(comp_key, 1l)
    assert compencrypted0 < MAXLONG128
    assert compencrypted1 < MAXLONG128

    twiceencrypted0 = rsa_encrypt(comp_key, encrypted0)
    twiceencrypted1 = rsa_encrypt(comp_key, encrypted1)
    assert twiceencrypted0 < MAXLONG128
    assert twiceencrypted1 < MAXLONG128

    assert compencrypted0 == rsa_decrypt(key, twiceencrypted0)
    assert compencrypted1 == rsa_decrypt(key, twiceencrypted1)

    hcompencrypted0 = hash_element(compencrypted0)
    hcompecnrypted1 = hash_element(compencrypted1)
    assert isinstance(hcompencrypted0, str) and len(hcompencrypted0) == 20
    assert isinstance(hcompecnrypted1, str) and len(hcompecnrypted1) == 20

    assert hcompencrypted0 == hash_element(rsa_decrypt(key, twiceencrypted0))
    assert hcompecnrypted1 == hash_element(rsa_decrypt(key, twiceencrypted1))

    fakeinfohash = '296069              '
    assert long_to_bytes(rsa_decrypt(key, rsa_encrypt(key, bytes_to_long(fakeinfohash)))) == fakeinfohash

    random_large_string = ''.join(choice(ascii_uppercase + digits) for _ in range(100001))
    signature = rsa_sign(key, random_large_string)
    assert rsa_verify(key, random_large_string, signature)

    encrypted_str = encrypt_str(key, random_large_string)
    assert random_large_string == decrypt_str(key, encrypted_str)

    # performance
    random_list = [randint(0, maxint) for i in xrange(100)]

    t1 = time()
    encrypted_values = []
    for i, value in enumerate(random_list):
        encrypted_values.append(rsa_encrypt(key, value))

    t2 = time()
    for cipher in encrypted_values:
        rsa_decrypt(key, cipher)

    print "Encrypting took", t2 - t1
    print "Decrypting took", time() - t2




