from collections import defaultdict
from Crypto.Util.number import long_to_bytes, bytes_to_long
from gmpy import mpz, invert
from pyasn1.type import univ, namedtype
from pyasn1.codec.der import decoder

from Tribler.dispersy.crypto import ECCrypto

import sys
from traceback import print_exc

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

        assert self in self.ec

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

        return PointOnCurve(self, _x, _y)

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

# from http://www.ietf.org/rfc/rfc5480.txt
class PubECParameters(univ.Choice):
    componentType = namedtype.NamedTypes(
        namedtype.NamedType('namedCurve', univ.ObjectIdentifier()),
        namedtype.NamedType('implicitCurve', univ.Null()),
        namedtype.NamedType('specifiedCurv', univ.Any()))

class AlgorithmIdentifier(univ.Sequence):
    componentType = namedtype.NamedTypes(
        namedtype.NamedType('algorithm', univ.ObjectIdentifier()),
        namedtype.NamedType('parameters', PubECParameters()))

class SubjectPublicKeyInfo(univ.Sequence):
    componentType = namedtype.NamedTypes(
        namedtype.NamedType('algorithm', AlgorithmIdentifier()),
        namedtype.NamedType('subjectPublicKey', univ.BitString()))

# from http://www.ietf.org/rfc/rfc3279.txt
class Curve(univ.Sequence):
    componentType = namedtype.NamedTypes(
         namedtype.NamedType('a', univ.OctetString()),
         namedtype.NamedType('b', univ.OctetString()),
         namedtype.OptionalNamedType('seed', univ.BitString()))

class FieldID(univ.Sequence):
    componentType = namedtype.NamedTypes(
         namedtype.NamedType('fieldType', univ.ObjectIdentifier("1")),
         namedtype.NamedType('parameters', univ.Any()))

class ECParameters(univ.Sequence):
    componentType = namedtype.NamedTypes(
         namedtype.NamedType('version', univ.Integer()),
         namedtype.NamedType('fieldID', FieldID()),
         namedtype.NamedType('curve', Curve()),
         namedtype.NamedType('base', univ.OctetString()),
         namedtype.NamedType('order', univ.Integer()),
         namedtype.OptionalNamedType('cofactor', univ.Integer()))

class EcpkParameters(univ.Choice):
    componentType = namedtype.NamedTypes(
        namedtype.NamedType('ecParameters', ECParameters()),
        namedtype.NamedType('namedCurve', univ.ObjectIdentifier()),
        namedtype.NamedType('implicitlyCA', univ.Null()))

class OpenSSLCurves():

    def __init__(self):
        self.curve_dict = defaultdict(lambda: ["", "", ""])

        implicit = False
        f = open('curves.ec', 'r')
        for line in f:
            line = line.strip()

            if not (line.startswith('#') or line.startswith('-----BEGIN')):
                if line.startswith('===') and line.endswith('==='):
                    curname = line[3:-3]
                elif line.startswith('-----END'):
                    self.curve_dict[curname][1 if implicit else 2] = self.curve_dict[curname][1 if implicit else 2].decode("BASE64")
                    implicit = not implicit
                else:
                    self.curve_dict[curname][1 if implicit else 2] += line
        f.close()

        for curvename, curve in self.curve_dict.items():
            try:
                decoded_implicit, _ = decoder.decode(curve[1])
                curve[1] = str(decoded_implicit)
            except:
                print >> sys.stderr, "Could not decode", curvename
                del self.curve_dict[curvename]

    def get_curve_for_public_key(self, key):
        ec = ECCrypto()
        der_encoded_str = ec.key_to_bin(key.pub())

        decoded_pk, _ = decoder.decode(der_encoded_str, asn1Spec=SubjectPublicKeyInfo())
        return self.get_curve(str(decoded_pk[0]['parameters']['namedCurve']))

    def get_curve(self, namedCurve):
        for curvename, curve in self.curve_dict.iteritems():
            if namedCurve == curve[1]:
                if not isinstance(curve[2], EllipticCurve):
                    try:
                        decoded_explicit, _ = decoder.decode(curve[2], asn1Spec=EcpkParameters())

                        coef_a = long(str(decoded_explicit[0]['curve']['a']).encode('HEX'), 16)
                        coef_b = long(str(decoded_explicit[0]['curve']['b']).encode('HEX'), 16)
                        modulo = long(str(decoded_explicit[0]['order']))
                        base_x, base_y = self.parse_ecpoint(str(decoded_explicit[0]['base']))
                        curve[2] = EllipticCurve(coef_a, coef_b, modulo, base_x, base_y)
                    except:
                        print >> sys.stderr, "Could not decode", curvename
                        print_exc()

                return curve[2]

    def parse_ecpoint(self, ecpoint):
        # uncompressed ecpoints start with 04 and then the two points
        hexstr = ecpoint.encode('HEX')
        if hexstr[:2] == '04':
            hexstr = hexstr[2:]
            return long(hexstr[:len(hexstr) / 2], 16), long(hexstr[len(hexstr) / 2:], 16)
