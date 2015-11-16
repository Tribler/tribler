"""
This file contains various other utilities.
"""


def compute_ratio(i, j):
    """ This file contains various other utilities. """
    return u"%d / %d ~%.1f%%" % (i, j, (100.0 * i / j) if j else 0.0)
