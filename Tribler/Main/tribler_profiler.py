# Requires yappi to be installed, use easy_install yappi
import os
import logging.config
from time import time

import yappi

from tribler import run

logger = logging.getLogger(__name__)


def run_tribler_with_yappi(run_function=None):
    t1 = time()

    # Start yappi
    yappi.start()

    # Do we have a custom run function?
    if run_function:
        run_function()
    else:  # Default to the normal run function
        run()

    # Stop yappi and get the results
    yappi.stop()
    logger.info("YAPPI: %s tribler has run for %s seconds", yappi.get_clock_type(), time() - t1)
    yappi_stats = yappi.get_func_stats()
    yappi_stats.sort("tsub")

    # If a yappi output dir is specified, save the output in callgrind format.
    if "YAPPI_OUTPUT_DIR" in os.environ:
        output_dir = os.environ["YAPPI_OUTPUT_DIR"]
        fname = os.path.join(output_dir, 'yappi.callgrind')
        yappi_stats.save(fname, type='callgrind')

    # Log the 50 most time consuming functions.
    count = 0
    for func_stat in yappi_stats:
        logger.info("YAPPI: %10dx  %10.3fs %s", func_stat.ncall, func_stat.tsub, func_stat.name)
        count += 1
        if count >= 50:
            break


if __name__ == '__main__':
    run_tribler_with_yappi()
