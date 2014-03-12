import logging
import logging.config

logger = logging.getLogger(__name__)

try:
    logging.config.fileConfig("logger.conf")
except:
    logger.exception("Unable to load logging config from 'logger.conf' file.")
logging.basicConfig(format="%(asctime)-15s [%(levelname)s] %(message)s")


# set wxpython version
try:
    import wxversion
    wxversion.select("2.8-unicode")
except:
    logger.exception("Unable to use wxversion, Error: %s.")


def run():
    from Tribler.Main.tribler_main import run as run_main
    run_main()

if __name__ == '__main__':
    run()
