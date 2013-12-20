from collections import defaultdict, namedtuple
from Crypto.Util.number import long_to_bytes, bytes_to_long
from gmpy import mpz, invert
from pyasn1.type import univ, namedtype, tag
from pyasn1.codec.der import decoder

from Tribler.dispersy.crypto import ECCrypto

import sys
from traceback import print_exc
from M2Crypto.EC import EC_pub
import os

ECElgamalKey = namedtuple('ECElgamalKey', ['ec', 'x', 'Q', 'size', 'encsize'])
ECElgamalKey_Pub = namedtuple('ECElgamalKey_Pub', ['ec', 'Q', 'size', 'encsize'])

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
    def to_bytes(point, length_bytes):
        return long_to_bytes(point.x, length_bytes) + long_to_bytes(point.y, length_bytes)

    @staticmethod
    def from_bytes(str_bytes, length_bytes):
        return Point(bytes_to_long(str_bytes[:length_bytes]), bytes_to_long(str_bytes[length_bytes:]))

class PointOnCurve(Point):
    __slots__ = ('ec')

    def __init__(self, ec, x, y):
        Point.__init__(self, x, y)
        self.ec = ec

        assert x < self.ec.q
        assert y < self.ec.q
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
            l = (mpz(3) * self.x * self.x + self.ec.a) * invert(2 * self.y, self.ec.q) % self.ec.q
        else:
            l = (b.y - self.y) * invert(b.x - self.x, self.ec.q) % self.ec.q

        x = (l * l - self.x - b.x) % self.ec.q
        y = (l * (self.x - x) - self.y) % self.ec.q
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
        return self.ec.point(self.x, -self.y % self.ec.q)

class EllipticCurve(object):
    """System of Elliptic Curve"""
    def __init__(self, a, b, q, base_x, base_y):
        """elliptic curve as: (y**2 = x**3 + a * x + b) mod q
        - a, b: params of curve formula
        - q: prime number
        """
        assert a < q
        assert 0 < b
        assert b < q
        assert q > 2
        assert (4 * (a ** 3) + 27 * (b ** 2)) % q != 0

        self.a = mpz(a)
        self.b = mpz(b)
        self.q = mpz(q)

        self.g = self.point(base_x, base_y)
        self.zero = self.point(0, 0)

    def point(self, x, y):
        _x = mpz(x)
        _y = mpz(y)

        return PointOnCurve(self, _x, _y)

    def convert_to_point(self, element):
        for i in xrange(1000):
            x = mpz(1000 * element + i)
            s = (x ** 3 + self.a * x + self.b) % self.q
            if pow(s, (self.q - 1) / 2, self.q) != 1:
                continue
            return self.point(x, pow(s, (self.q + 1) / 4, self.q))

    def convert_to_long(self, point):
        return long(point.x / 1000)

    def __contains__(self, p):
        # elliptic curve is defined as: (y**2 = x**3 + a * x + b) mod q
        # hence a point should adhere to this equation
        if p.is_zero(): return True
        l = pow(p.y, 2, self.q)
        r = (pow(p.x, 3, self.q) + (self.a * p.x) + self.b) % self.q
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

# from http://tools.ietf.org/html/rfc5915

taggedBitString = univ.BitString().subtype(implicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatSimple, 1))
taggedECParameters = PubECParameters().subtype(implicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatSimple, 0))

class ECPrivateKey(univ.Sequence):
    componentType = namedtype.NamedTypes(
        namedtype.NamedType('version', univ.Integer()),
        namedtype.NamedType('privateKey', univ.OctetString()),
        namedtype.NamedType('parameters', taggedECParameters),
        namedtype.OptionalNamedType('publicKey', taggedBitString))

# from http://www.ietf.org/rfc/rfc3279.txt
class Pentanomial(univ.Sequence):
    componentType = namedtype.NamedTypes(
         namedtype.NamedType('k1', univ.Integer()),
         namedtype.NamedType('k2', univ.Integer()),
         namedtype.NamedType('k3', univ.Integer()))

class CharacteristicTwo(univ.Sequence):
    componentType = namedtype.NamedTypes(
         namedtype.NamedType('m', univ.Integer()),
         namedtype.NamedType('basis', univ.ObjectIdentifier()),
         namedtype.NamedType('parameters', univ.Any()))

class Curve(univ.Sequence):
    componentType = namedtype.NamedTypes(
         namedtype.NamedType('a', univ.OctetString()),
         namedtype.NamedType('b', univ.OctetString()),
         namedtype.OptionalNamedType('seed', univ.BitString()))

class FieldID(univ.Sequence):
    componentType = namedtype.NamedTypes(
         namedtype.NamedType('fieldType', univ.ObjectIdentifier()),
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

        implicit = True
        f = open(os.path.join(os.path.dirname(__file__), 'curves.ec'), 'r')
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

    def get_curve_for_key(self, key):
        ec = ECCrypto()
        der_encoded_str = ec.key_to_bin(key)

        decoded_pk, _ = decoder.decode(der_encoded_str, asn1Spec=SubjectPublicKeyInfo())
        return self.get_curve(str(decoded_pk[0]['parameters']['namedCurve']))

    def get_ecelgamalkey_for_key(self, key):
        ec = ECCrypto()
        size = ec.get_signature_length(key) / 2

        der_encoded_str = ec.key_to_bin(key)

        if isinstance(key, EC_pub):
            decoded_pk, _ = decoder.decode(der_encoded_str, asn1Spec=SubjectPublicKeyInfo())
            curve = self.get_curve(str(decoded_pk[0]['parameters']['namedCurve']))
            bitstring = "".join(map(str, decoded_pk[1]))

            x = None
        else:
            decoded_pk, _ = decoder.decode(der_encoded_str, asn1Spec=ECPrivateKey())
            curve = self.get_curve(str(decoded_pk['parameters']['namedCurve']))
            bitstring = "".join(map(str, decoded_pk['publicKey']))

            x = self.os2ip(decoded_pk['privateKey'].asNumbers())

        octetstring = str(univ.OctetString(binValue=bitstring))
        Q = curve.point(*self.parse_ecpoint(octetstring))
        if x:
            return ECElgamalKey(curve, x, Q, size, size * 4)
        return ECElgamalKey_Pub(curve, Q, size, size * 4)


    def get_curve(self, namedCurve):
        for curve in self.curve_dict.itervalues():
            if namedCurve == curve[1]:
                if not isinstance(curve[2], EllipticCurve):
                    decoded_explicit, _ = decoder.decode(curve[2], asn1Spec=EcpkParameters())

                    fieldType = decoded_explicit[0]['fieldID']['fieldType'][-1]
                    if fieldType == 1:
                        modulo, _ = decoder.decode(decoded_explicit[0]['fieldID']['parameters'], asn1Spec=univ.Integer())
                        modulo = long(modulo)
                    else:
                        raise RuntimeError('no clue how to decode modulo')

#                     elif fieldType == 2:
#                         decoded_explicit[0]['fieldID']['parameters'], _ = decoder.decode(decoded_explicit[0]['fieldID']['parameters'], asn1Spec=CharacteristicTwo())
#
#                         if decoded_explicit[0]['fieldID']['parameters']['basis'][-1] == 3:
#                             decoded_explicit[0]['fieldID']['parameters']['parameters'], _ = decoder.decode(decoded_explicit[0]['fieldID']['parameters']['parameters'], asn1Spec=Pentanomial())

                    coef_a = long(str(decoded_explicit[0]['curve']['a']).encode('HEX'), 16)
                    coef_b = long(str(decoded_explicit[0]['curve']['b']).encode('HEX'), 16)
                    base_x, base_y = self.parse_ecpoint(str(decoded_explicit[0]['base']))
                    curve[2] = EllipticCurve(coef_a, coef_b, modulo, base_x, base_y)
                return curve[2]

    def parse_ecpoint(self, ecpoint):
        # uncompressed ecpoints start with 04 and then the two points
        hexstr = ecpoint.encode('HEX')
        if hexstr[:2] == '04':
            hexstr = hexstr[2:]
            return long(hexstr[:len(hexstr) / 2], 16), long(hexstr[len(hexstr) / 2:], 16)
        else:
            raise RuntimeError('no clue how to decode ecpoint')

    def os2ip(self, octects_list):
        x = 0
        for i, xleni in enumerate(reversed(octects_list)):
            x += xleni * (256 ** i)

        return x
