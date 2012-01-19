#Requires yappi to be installed, use easy_install yappi

import yappi
from tribler import run

if __name__ == '__main__':
    yappi.start()
    run()
    yappi.print_stats(yappi.SORTTYPE_TTOTAL)
