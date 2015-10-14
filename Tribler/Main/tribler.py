import logging.config
import sys
import os

if sys.platform == 'win32':
    import win32api
    path_env = win32api.GetEnvironmentVariableW(u'PATH')
    path_env = os.path.abspath(u'vlc') + os.pathsep + path_env
    path_env = os.path.abspath(u'.') + os.pathsep + path_env
    win32api.SetEnvironmentVariableW(u'PATH', path_env)

    # CHDIR to the install dir in case Tribler gets called to open a .torrent
    # file (which will make Windows set PWD to the torrent file location)
    os.chdir(os.path.dirname(sys.argv[0]))

try:
    filepath = os.path.abspath(u"logger.conf")
    logging.config.fileConfig(filepath)
except Exception as e:
    print >> sys.stderr, u"Unable to load logging config from '%s' file: %s" % (repr(filepath), repr(e))
    print >> sys.stderr, u"Current working directory: %s" % repr(os.path.abspath(u'.'))
    if not os.path.exists(filepath):
        print >> sys.stderr, "File doesn't exist"
    elif not os.path.isfile(filepath):
        print >> sys.stderr, "It is not a file"
    else:
        print >> sys.stderr, "logger.conf file contents follow:"
        print >> sys.stderr, "8<--------------" * 5

        with open(filepath, 'r') as conf:
            print >> sys.stderr, conf.read()

        print >> sys.stderr,  "8<--------------" * 5


logging.basicConfig(format="%(asctime)-15s [%(levelname)s] %(message)s")

logger = logging.getLogger(__name__)

# This import needs to be before any twisted or dispersy import so it can initalize the reactor in a separate thread
# No need to do reactor.run(), it gets started when imported
from Tribler.Core.Utilities.twisted_thread import reactor, stop_reactor

# set wxpython version
import wxversion
try:
    # in the windows and mac distribution, there may be no version available.
    # so select a version only when there is any available.
    if wxversion.getInstalled():
        wxversion.select("2.8-unicode")
except wxversion.VersionError:
    logger.exception("Unable to use wxversion installed wxversions: %s", repr(wxversion.getInstalled()))


def run():
    from Tribler.Main.tribler_main import run as run_main
    run_main()

if sys.version_info[:2] != (2, 7):
    print >> sys.stderr, "Tribler needs python 2.7.X to run, current version: %s" % sys.version
    exit(1)

if __name__ == '__main__':

    run()
    delayed_calls = reactor.getDelayedCalls()
    if delayed_calls:
        print >> sys.stderr, "The reactor was not clean after stopping:"
        for dc in delayed_calls:
            print >> sys.stderr, ">     %s" % dc

    stop_reactor()
