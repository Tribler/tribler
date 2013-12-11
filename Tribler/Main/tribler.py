import sys
import logging.config
try:
    logging.config.fileConfig("logger.conf")
except:
    print >> sys.stderr, "Unable to load logging config from 'logger.conf' file."
logging.basicConfig(format="%(asctime)-15s [%(levelname)s] %(message)s")

from tribler_main import run as run_main

def run():
    run_main()

if __name__ == '__main__':
    run()
