from Tribler.Utilities.X11 import init_X11
init_X11()


import logging.config


logger = logging.getLogger(__name__)

try:
    logging.config.fileConfig("logger.conf")
except:
    logger.exception("Unable to load logging config from 'logger.conf' file.")
logging.basicConfig(format="%(asctime)-15s [%(levelname)s] %(message)s")

# This import needs to be before any twisted or dispersy import so it can initalize the reactor in a separate thread
# No need to do reactor.run(), it gets started when imported
from Tribler.Core.Utilities.twisted_thread import reactor, stop_reactor

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
    stop_reactor()
