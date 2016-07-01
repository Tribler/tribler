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

# tribler_exe.py: does this for windows in an uglier way.
if sys.platform != 'win32':
    # Make sure the installation dir is on the PATH
    os.environ['PATH'] = os.path.abspath(TRIBLER_ROOT) + os.pathsep + os.environ['PATH']

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


if sys.version_info[:2] != (2, 7):
    print >> sys.stderr, "Tribler needs python 2.7.X to run, current version: %s" % sys.version
    exit(1)


def __main__():
    from twisted.scripts.twistd import run
    run()


if __name__ == '__main__':
    __main__()
