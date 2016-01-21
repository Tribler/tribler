#!/usr/bin/env python
import logging.config
import sys
import os


from Tribler.Core.Utilities.install_dir import determine_install_dir
# This should work for Linux, Windows and OSX
TRIBLER_ROOT = determine_install_dir()
LOGGER_CONF = os.path.join(TRIBLER_ROOT, "logger.conf")

# Add TRIBLER_ROOT to the PYTHONPATH so imports work fine wherever Tribler is
# running from.
if TRIBLER_ROOT not in sys.path:
    sys.path.insert(0, TRIBLER_ROOT)

try:
    logging.config.fileConfig(LOGGER_CONF)
except Exception as e:
    print >> sys.stderr, u"Unable to load logging config from '%s' file: %s" % (repr(LOGGER_CONF), repr(e))
    print >> sys.stderr, u"Current working directory: %s" % repr(os.path.abspath(u'.'))
    if not os.path.exists(LOGGER_CONF):
        print >> sys.stderr, "File doesn't exist"
    elif not os.path.isfile(LOGGER_CONF):
        print >> sys.stderr, "It is not a file"
    else:
        print >> sys.stderr, "logger.conf file contents follow:"
        print >> sys.stderr, "8<--------------" * 5

        with open(LOGGER_CONF, 'r') as conf:
            print >> sys.stderr, conf.read()

        print >> sys.stderr, "8<--------------" * 5


logging.basicConfig(format="%(asctime)-15s [%(levelname)s] %(message)s")

logger = logging.getLogger(__name__)

# This import needs to be before any twisted or dispersy import so it can initalize the reactor in a separate thread
# No need to do reactor.run(), it gets started when imported
from Tribler.Core.Utilities.twisted_thread import reactor, stop_reactor

from Tribler.Main.Utility.utility import initialize_x11_threads
initialize_x11_threads()

# set wxpython version
import wxversion
try:
    # in the windows and mac distribution, there may be no version available.
    # so select a version only when there is any available.
    if wxversion.getInstalled():
        if wxversion.checkInstalled("3.0-unicode"):
            wxversion.select("3.0-unicode")
        else:
            wxversion.select("2.8-unicode")
except wxversion.VersionError:
    logger.exception("Unable to use wxversion installed wxversions: %s", repr(wxversion.getInstalled()))


def run():
    from Tribler.Main.tribler_main import run as run_main
    run_main()

if sys.version_info[:2] != (2, 7):
    print >> sys.stderr, "Tribler needs python 2.7.X to run, current version: %s" % sys.version
    exit(1)

# Windows py2exe freezing tribler.py wreaks havoc with paths, imports, etc. So a
# tribler_exe.py module has been created which only role is to find this module
# (tribler.py), import __main__ and call it. The former is the one that will be
# frozen by py2exe. Any other OSes can keep calling tribler.py just fine.

def __main__():
    """
    Run Tribler and check if the reactor is dirty when shutting down.

    This method is also called from tribler_exe.py.
    """
    run()
    delayed_calls = reactor.getDelayedCalls()
    if delayed_calls:
        print >> sys.stderr, "The reactor was not clean after stopping:"
        for dc in delayed_calls:
            print >> sys.stderr, ">     %s" % dc

    stop_reactor()

if __name__ == '__main__':
    __main__()
