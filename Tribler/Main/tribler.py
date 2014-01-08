#!/usr/bin/python

import sys
import logging.config
try:
    logging.config.fileConfig("logger.conf")
except:
    print >> sys.stderr, "Unable to load logging config from 'logger.conf' file."

def run():
    from Tribler.Main.tribler_main import run as run_main
    run_main()

if __name__ == '__main__':
    run()
