# Requires yappi to be installed, use easy_install yappi

import yappi
import sys
from time import time
from tribler import run

if __name__ == '__main__':
    t1 = time()
    yappi.start()
    run()
    yappi.stop()
    print >> sys.stderr, "YAPPI: %s tribler has run for %s seconds" % \
        (yappi.get_clock_type(), time() - t1)
    yappi_stats = yappi.get_func_stats()
    yappi_stats.sort("tsub")
    count = 0
    for func_stat in yappi_stats:
        print >> sys.stderr, "YAPPI: %10dx  %10.3fs %s" % \
            (func_stat.ncall, func_stat.tsub, func_stat.name)
        count += 1
        if count >= 50:
            break
