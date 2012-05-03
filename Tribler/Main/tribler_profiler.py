#Requires yappi to be installed, use easy_install yappi

import yappi
from tribler import run

if __name__ == '__main__':
    yappi.start()
    run()
    stats = yappi.get_stats(yappi.SORTTYPE_TSUB)
    for func_stats in stats.func_stats[:50]:
        print "YAPPI: %10dx  %10.3fs" % (func_stats.ncall, func_stats.tsub), func_stats.name

    #yappi.print_stats(yappi.SORTTYPE_TTOTAL)
