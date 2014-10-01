import logging.config
import sys

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
    wxversion.select("2.9")
except:
    logger.exception("Unable to use wxversion, Error: %s.")

def run():
    from Tribler.Main.tribler_main import run as run_main
    run_main()

if __name__ == '__main__':
    run()
    delayed_calls = reactor.getDelayedCalls()
    if delayed_calls:
        print >> sys.stderr, "The reactor was not clean after stopping:"
        for dc in delayed_calls:
            print >> sys.stderr, ">     %s" % dc

    stop_reactor()
