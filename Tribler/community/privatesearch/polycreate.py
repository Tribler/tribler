from itertools import product, groupby
from random import Random
from time import time

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
    def multi(coefficient):
        power = len(coefficients) - coefficient - 1
        if power:
            return coefficients[coefficient] * pow(x, power)
        return coefficients[coefficient]

    result = multi(0)
    for index in range(1, len(coefficients)):
        result = result + multi(index)

    return result

if __name__ == "__main__":


    r = Random()
    set1 = [r.randint(0, 2 ** 25) for i in range(100)]
    print set1

    t1 = time()
    print compute_coeff(set1)
    print time() - t1

    coeff = compute_coeff(set1)
    for val in set1:
        print val, polyval(coeff, val)
#
#     nr_false_positive = 0
#     for _ in range(10000):
#         i = r.randint(0, 2 ** 25)
#         if i not in set1:
#             returnval = polyval(coeff, i)
#             if returnval == 0:
#                 nr_false_positive += 1
#     print nr_false_positive / 10000.0
