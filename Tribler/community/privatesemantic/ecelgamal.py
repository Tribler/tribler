# Based on https://gist.github.com/bellbind/1414867, added some
# https://github.com/gdcurt/eccrypto in the mix
# Modified by Niels Zeilemaker, optimized using mpz etc.

from collections import namedtuple
from random import randint, choice
from sys import maxint
from time import time

from gmpy import mpz, invert, rand

from cProfile import Profile
from Crypto.Random.random import StrongRandom
from string import ascii_uppercase, digits
from Crypto.Util.number import long_to_bytes, bytes_to_long
from Crypto.Cipher import AES

ECElgamalKey = namedtuple('ECElgamalKey', ['ec', 'x', 'Q', 'size', 'encsize'])

class Point(object):
    __slots__ = ('x', 'y')
    def __init__(self, x, y):
        self.x = x
        self.y = y

    def is_zero(self):
        return self.x == 0 and self.y == 0

    def __eq__(self, p):
        return self.x == p.x and self.y == p.y

    def __str__(self):
        return '(%d : %d)' % (self.x, self.y)

    @staticmethod
    def to_bytes(point, bits):
        return long_to_bytes(point.x, bits / 8) + long_to_bytes(point.y, bits / 8)

    @staticmethod
    def from_bytes(str_bytes, bits):
        return Point(bytes_to_long(str_bytes[:bits / 8]), bytes_to_long(str_bytes[bits / 8:]))

class PointOnCurve(Point):
    __slots__ = ('ec')

    def __init__(self, ec, x, y):
        Point.__init__(self, x, y)
        self.ec = ec

    def __add__(self, b):
        # <add> of elliptic curve: negate of 3rd cross point of (p1,p2) line
        if False:
            d = self +b
            assert self.ec.is_valid(d)
            assert d - b == self
            assert self -self == self.ec.zero
            assert self +b == b + self
            assert self +(b + d) == (self +b) + d

        if self.is_zero(): return b
        if b.is_zero(): return self
        if self == -b: return self.ec.zero
        if self == b:
            l = (mpz(3) * self.x * self.x + self.ec.a) * invert(2 * self.y, self.ec.modulus) % self.ec.modulus
        else:
            l = (b.y - self.y) * invert(b.x - self.x, self.ec.modulus) % self.ec.modulus

        x = (l * l - self.x - b.x) % self.ec.modulus
        y = (l * (self.x - x) - self.y) % self.ec.modulus
        return self.ec.point(x, y)

    def __sub__(self, p):
        return self.__add__(-p)

    def __rmul__(self, n):
        r = self.ec.zero

        result = self
        while 0 < n:
            if n & 1 == 1:
                r += result
            result = result + result
            n /= 2
        return r

    def __neg__(self):
        return self.ec.point(self.x, -self.y % self.ec.modulus)

class EllipticCurve(object):
    """System of Elliptic Curve"""
    def __init__(self, a, b, modulus, base_x, base_y):
        """elliptic curve as: (y**2 = x**3 + a * x + b) mod q
        - a, b: params of curve formula
        - modulus: prime number
        """
        assert a < modulus
        assert 0 < b
        assert b < modulus
        assert modulus > 2
        assert (4 * (a ** 3) + 27 * (b ** 2)) % modulus != 0

        self.a = mpz(a)
        self.b = mpz(b)
        self.modulus = mpz(modulus)

        self.g = self.point(base_x, base_y)
        self.zero = self.point(0, 0)

    def point(self, x, y):
        _x = mpz(x)
        _y = mpz(y)

        p = Point(_x, _y)
        if p in self:
            return PointOnCurve(self, _x, _y)
        else:
            raise RuntimeError('Point not in curve (%d,%d)' % (x, y))

    def convert_to_point(self, element):
        for i in xrange(1000):
            x = mpz(1000 * element + i)
            s = (x ** 3 + self.a * x + self.b) % self.modulus
            if pow(s, (self.modulus - 1) / 2, self.modulus) != 1:
                continue
            return self.point(x, pow(s, (self.modulus + 1) / 4, self.modulus))

    def convert_to_long(self, point):
        return long(point.x / 1000)

    def __contains__(self, p):
        if p.is_zero(): return True
        l = (p.y ** 2) % self.modulus
        r = ((p.x ** 3) + self.a * p.x + self.b) % self.modulus
        return l == r

    def from_bytes(self, str_bytes, bits):
        p = Point.from_bytes(str_bytes, bits)
        return self.point(p.x, p.y)

def ecelgamal_init(bits=192):
    curve = None

    if bits == 192:
        coef_a = -3
        coef_b = 0x64210519e59c80e70fa7e9ab72243049feb8deecc146b9b1
        modulus = 6277101735386680763835789423207666416083908700390324961279

        base_x = 0x188da80eb03090f67cbf20eb43a18800f4ff0afd82ff1012
        base_y = 0x07192b95ffc8da78631011ed6b24cdd573f977a11e794811
        curve = EllipticCurve(coef_a, coef_b, modulus, base_x, base_y)

    if bits == 256:
        coef_a = -3
        coef_b = 0x5ac635d8aa3a93e7b3ebbd55769886bc651d06b0cc53b0f63bce3c3e27d2604b
        modulus = 115792089210356248762697446949407573530086143415290314195533631308867097853951

        base_x = 0x6b17d1f2e12c4247f8bce6e563a440f277037d812deb33a0f4a13945d898c296
        base_y = 0x4fe342e2fe1a7f9b8ee7eb4a7c0f9e162bce33576b315ececbb6406837bf51f5
        curve = EllipticCurve(coef_a, coef_b, modulus, base_x, base_y)

    if bits == 384:
        coef_a = -3
        coef_b = 0xb3312fa7e23ee7e4988e056be3f82d19181d9c6efe8141120314088f5013875ac656398d8a2ed19d2a85c8edd3ec2aef
        modulus = 39402006196394479212279040100143613805079739270465446667948293404245721771496870329047266088258938001861606973112319
        base_x = 0xaa87ca22be8b05378eb1c71ef320ad746e1d3b628ba79b9859f741e082542a385502f25dbf55296c3a545e3872760ab7
        base_y = 0x3617de4a96262c6f5d9e98bf9292dc29f8f41dbd289a147ce9da3113b5f0b8c00a60b1ce1d7e819d7a431d7c90ea0e5f
        curve = EllipticCurve(coef_a, coef_b, modulus, base_x, base_y)

    if bits == 521:
        coef_a = -3
        coef_b = 0x051953eb9618e1c9a1f929a21a0b68540eea2da725b99b315f3b8b489918ef109e156193951ec7e937b1652c0bd3bb1bf073573df883d2c34f1ef451fd46b503f00
        modulus = 6864797660130609714981900799081393217269435300143305409394463459185543183397656052122559640661454554977296311391480858037121987999716643812574028291115057151
        base_x = 0xc6858e06b70404e9cd9e3ecb662395b4429c648139053fb521f828af606b4d3dbaa14b5e77efe75928fe1dc127a2ffa8de3348b3c1856a429bf97e7e31c2e5bd66
        base_y = 0x11839296a789a3bc0045c8a5fb42c7d1bd998f54449579b446817afbd17273e662c97ee72995ef42640c550b9013fad0761353c7086a272c24088be94769fd16650
        curve = EllipticCurve(coef_a, coef_b, modulus, base_x, base_y)

    if curve:
        rand('init', 128)
        rand('seed', StrongRandom().randint(0, maxint))
        x = rand('next', 10000)
        Q = x * curve.g
        return ECElgamalKey(curve, x, Q, bits, bits * 4)

def ecelgamal_encrypt(key, M):
    assert M in key.ec
    k = rand('next', 10000)

    R = k * key.ec.g
    S = M + k * key.Q
    return (R, S)

def ecelgamal_decrypt_str(key, cipher):
    assert isinstance(cipher, str), type(cipher)
    R = key.ec.from_bytes(cipher[:key.encsize / 8 / 2], key.size)
    S = key.ec.from_bytes(cipher[key.encsize / 8 / 2:], key.size)

    M = ecelgamal_decrypt(key, (R, S))
    return key.ec.convert_to_long(M)

def ecelgamal_decrypt(key, cipher):
    R, S = cipher
    M = S - key.x * R
    return M

def ecelgamal_add(cipher1, cipher2):
    R = cipher1[0] + cipher2[0]
    S = cipher1[1] + cipher2[1]
    return R, S

def encrypt_str(key, plain_str):
    aes_key = StrongRandom().getrandbits(128)
    cipher = AES.new(long_to_bytes(aes_key, 16), AES.MODE_CFB, '\x00' * 16)

    enc_str = cipher.encrypt(plain_str)

    R, S = ecelgamal_encrypt(key, key.ec.convert_to_point(aes_key))
    enc_aes_key = Point.to_bytes(R, key.size) + Point.to_bytes(S, key.size)
    return enc_aes_key + enc_str

def decrypt_str(key, encr_str):
    enc_aes_key = encr_str[:key.encsize / 8]

    R = key.ec.from_bytes(enc_aes_key[:key.encsize / 8 / 2], key.size)
    S = key.ec.from_bytes(enc_aes_key[key.encsize / 8 / 2:], key.size)
    M = ecelgamal_decrypt(key, (R, S))
    aes_key = key.ec.convert_to_long(M)

    cipher = AES.new(long_to_bytes(aes_key, 16), AES.MODE_CFB, '\x00' * 16)
    plain_str = cipher.decrypt(encr_str[key.encsize / 8:])
    return plain_str

if __name__ == "__main__":
    # lets check if this ecelgamal thing works
    key = ecelgamal_init()

    M1 = key.ec.convert_to_point(1)
    M2 = key.ec.convert_to_point(2)

    assert key.ec.convert_to_long(M1) == 1, key.ec.convert_to_int(M1)
    assert key.ec.convert_to_long(M2) == 2, key.ec.convert_to_int(M2)

    encr_1 = ecelgamal_encrypt(key, M1)
    encr_2 = ecelgamal_encrypt(key, M2)

    M1M2 = ecelgamal_decrypt(key, ecelgamal_add(encr_1, encr_2))

    assert key.ec.convert_to_long(M1M2 - M2) == 1
    assert key.ec.convert_to_long(M1M2 - M1) == 2

    random_large_string = ''.join(choice(ascii_uppercase + digits) for _ in range(100001))
    encrypted_str = encrypt_str(key, random_large_string)
    assert random_large_string == decrypt_str(key, encrypted_str)

    # performance
    def do_perf():
        t1 = time()
        random_list = [key.ec.convert_to_point(randint(0, maxint)) for _ in xrange(10000)]
        t2 = time()

        encrypted_values = []
        for i, value in enumerate(random_list):
            encrypted_values.append(ecelgamal_encrypt(key, value))

        t3 = time()
        for cipher in encrypted_values:
            ecelgamal_decrypt(key, cipher)

        print "Took %.2fs to encrypt %d points, %.2fs to decrypt them (%.2fs to generate the points)" % (t3 - t2, len(random_list), time() - t3, t2 - t1)

    profiler = Profile()
    profiler.runcall(do_perf)
    profiler.print_stats()
