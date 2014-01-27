# Requires yappi to be installed, use easy_install yappi

import yappi
from tribler import run
from time import time
import logging

logger = logging.getLogger(__name__)

if __name__ == '__main__':
    t1 = time()
    yappi.start()
    run()
    yappi.stop()
    logger.info("YAPPI: %s tribler has run for %s seconds", yappi.clock_type(), time() - t1)
    stats = yappi.get_stats(yappi.SORTTYPE_TSUB)
    for func_stats in stats.func_stats[:50]:
        logger.info("YAPPI: %10dx  %10.3fs %s", func_stats.ncall, func_stats.tsub, func_stats.name)

    # yappi.print_stats(yappi.SORTTYPE_TTOTAL)
