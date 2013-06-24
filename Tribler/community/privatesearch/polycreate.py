from itertools import product, groupby
from random import Random
from time import time

from gmpy import mpz

class X:
    def __init__(self, val, power):
        self.val = val
        self.power = power

    def multiply(self, other):
        return X(self.val * other.val, self.power + other.power)

    def merge(self, other):
        assert self.power == other.power
        self.val += other.val

    def __repr__(self):
        if self.power:
            if self.val == 1:
                return "X^%d" % self.power
            if self.val == -1:
                return "-X^%d" % self.power
            return "%dX^%d" % (self.val, self.power)
        return "%d" % self.val

def multiply(terms):
    if len(terms) == 1:
        return terms[0]

    me = terms[0]
    other = terms[1]
    if len(terms) > 2:
        other = multiply(terms[1:])

    combinations = product(me, other)
    results = [a.multiply(b) for a, b in combinations]
    results.sort(cmp=lambda a, b : cmp(a.power, b.power), reverse=True)
    merged_results = []
    for _, g in groupby(results, lambda x: x.power):
        g = list(g)
        first = g[0]
        g = g[1:]
        while len(g):
            first.merge(g[0])
            g = g[1:]
        merged_results.append(first)
    return merged_results

def compute_coeff(roots):
    terms = [[X(1, 1), X(-root, 0)] for root in roots]
    coeffs = multiply(terms)
    return [coeff.val for coeff in coeffs]

def polyval(coefficients, x):
    result = 0
    for coefficient in coefficients:
        result = result * x + coefficient
    return result

if __name__ == "__main__":
    r = Random()
    set1 = [r.randint(0, 2 ** 32) for i in range(100)]
    print set1

    t1 = time()
    print compute_coeff(set1)
    print time() - t1

    coeff = compute_coeff(set1)
    for val in set1:
        print val, polyval(coeff, val)

    t1 = time()
    nr_false_positive = 0
    for _ in range(100000):
        i = r.randint(0, 2 ** 32)
        if i not in set1:
            returnval = polyval(coeff, i)
            if returnval == 0:
                nr_false_positive += 1
    print time() - t1, nr_false_positive / 100000.0
