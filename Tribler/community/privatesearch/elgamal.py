# from Crypto.PublicKey import ElGamal
# from Crypto import Random
# from Crypto.Random.random import StrongRandom
# from Crypto.Util.number import GCD, inverse
# from gmpy import mpz

from hashlib import md5

from time import time
from collections import namedtuple
from random import randint, Random

import numpy
from matplotlib.pyplot import *
from traceback import print_exc
from numpy.polynomial.chebyshev import chebfromroots
from numpy.polynomial.polynomial import polyfromroots

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
#     r = Random()
#
#     for universe in range(8, 32, 8):
#         for roots in range(1, 101):
#             set1 = [r.randint(0, 2 ** universe) for i in range(roots)]
#             y1 = [0] * len(set1)
#
#             set1.insert(0, 0)
#             y1.insert(0, 1)
#
#             for coeff in [100, 32, 16]:
#                 try:
#                     a = numpy.polyfit(set1, y1, coeff)
#                     b = numpy.roots(a)
#
#                     f = open("output/%d.%d.%d_coeff.txt" % (universe, coeff, roots), "w")
#                     print >> f, ";".join(["%.15f" % val for val in a])
#                     f.close()
#
#                     f = open("output/%d.%d.%d_roots.txt" % (universe, coeff, roots), "w")
#
#                     b = [val for val in b]
#                     b.sort()
#
#                     c = set1[1:]
#                     c.sort()
#
#                     for got, expected in zip(b, c):
#                         print >> f, "%.15f\t\t%d" % (got, expected)
#
#                     f.close()
#                 except:
#                     print_exc()
#
#
    r = Random()
    set1 = [r.randint(0, 2 ** 25) for i in range(10)]
    set1.sort()
    a = chebfromroots(set1)
    b = polyfromroots(set1)
    c = numpy.polyfit([0] + set1, [1] + [0] * len(set1), 10)
    print a
    print b
    print c

    polynomial = numpy.poly1d(a)
    ys = polynomial(set1)

    polynomial = numpy.poly1d(b)
    ys2 = polynomial(set1)

    polynomial = numpy.poly1d(c)
    ys3 = polynomial(set1)

    ar = numpy.roots(a)
    ar = [val for val in ar]
    ar.sort()

    br = numpy.roots(b)
    br = [val for val in br]
    br.sort()

    cr = numpy.roots(c)
    cr = [val for val in cr]
    cr.sort()

    for gota, gotb, gotc, actual in zip(ar, br, cr, set1):
        print gota, gotb, gotc, actual

    plot(set1, [0] * len(set1), 'o')
    plot(set1, ys)
    plot(set1, ys2)
    plot(set1, ys3)
    ylabel('y')
    xlabel('x')
    xlim(0, 2 ** 25)
    show()

#
#
#
#
#
#     r = Random()
#     set1 = [r.randint(0, 2 ** 25) for i in range(3)]
#     set2 = [r.randint(0, 2 ** 32) for i in range(100, 200)]
#     set1.sort()
#     set2.sort()
#
#
#     # result = numpy.poly(set1)
#
#
#     y1 = [0] * len(set1)
#     y2 = [0] * len(set2)
#
#     set1.insert(0, 0)
#     y1.insert(0, 1)
#
# #    degree = len(set1)
# #    breakNext = False
# #    while True:
# #        try:
# #            a = numpy.polyfit(set1, y1, degree)
# #            if breakNext:
# #                break
# #
# #            degree = sum(bool(i) for i in a) - 1
# #            breakNext = True
# #        except:
# #            degree -= 1
#
#     a = numpy.polyfit(set1, y1, 3)
#     b = numpy.roots(a)
#     b.sort()
#
#     c = numpy.poly(set1[1:])
#     d = numpy.roots(c)
#     d.sort()
#
#     print a
#     print b
#     print c
#     print d
#     print set1
#
# #    print sum(a)
# #    print set1
# #    print y1
# #    print a, len(a), sum(bool(i) for i in a)
#
#     lower = -0.0000001
#     upper = 0.0000001
#
#     nr_false_positive = 0
#     for _ in range(100000):
#         i = randint(0, 2 ** 25)
#         if i not in set1:
#             returnval = numpy.polyval(a, i)
#             if lower < returnval < upper:
#                 nr_false_positive += 1
#
#     nr_positive = 0
#     for i in set1:
#         returnval = numpy.polyval(a, i)
#         # print returnval, i, lower < returnval < upper
#         if lower < returnval < upper:
#             nr_positive += 1
#             print i, returnval
#
#     print nr_false_positive / float(100000), nr_positive / float(len(set1) - 1)
#
#
#     polynomial = numpy.poly1d(a)
#     ys = polynomial(set1)
#
#     plot(set1, y1, 'o')
#     plot(set1, ys)
#     ylabel('y')
#     xlabel('x')
#     xlim(0, 2 ** 25)
#     ylim(-0.0001, 0.0001)
#     show()


#     for i in a:
#         if i:
#             if i in seen_values:
#                 known_values += 1
#             seen_values.add(i)
#     print known_values, len(seen_values)

    # lets check if this elgamal thing works
#     t1 = time()
#     key = elgamal_init(1024)
#
#     t2 = time()
#     encrypted3 = elgamal_encrypt(key, 3l)
#
#     t3 = time()
#     encrypted2 = elgamal_encrypt(key, 2l)
#
#     t4 = time()
#     encrypted6 = (encrypted3[0] * encrypted2[0], encrypted3[1] * encrypted2[1])
#
#     t5 = time()
#
#     print elgamal_decrypt(key, encrypted6)
#     print time() - t5, t5 - t4, t4 - t3, t3 - t2, t2 - t1
