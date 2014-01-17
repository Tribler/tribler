import sys
import logging
import logging.config

logger = logging.getLogger(__name__)

try:
    logging.config.fileConfig("logger.conf")
except:
    logger.error("Unable to load logging config from 'logger.conf' file.")
logging.basicConfig(format="%(asctime)-15s [%(levelname)s] %(message)s")


def run():
    from Tribler.Main.tribler_main import run as run_main
    run_main()

if __name__ == '__main__':
    run()
