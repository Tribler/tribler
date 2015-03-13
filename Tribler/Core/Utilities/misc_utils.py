def compute_ratio(i, j):
    return u"%d / %d ~%.1f%%" % (i, j, (100.0 * i / j) if j else 0.0)
