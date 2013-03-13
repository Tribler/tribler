# Written by Arno Bakker
# Updated by George Milescu
# see LICENSE.txt for license information
#
# Razvan Deaconescu, 2008:
#       * corrected problem when running in background
#       * added usage and print_version functions
#       * uses getopt for command line argument parsing

import sys
import shutil
import time
import tempfile
import random
import os
import getopt
from traceback import print_exc

from Tribler.Core.API import *
from Tribler.Core.__init__ import version, report_email

# Print usage message
def usage():
    print "Usage: python cmdlinedl.py [options] torrentfile_or_url"
    print "Options:"
    print "\t--port <port>"
    print "\t-p <port>\t\tuse <port> to listen for connections"
    print "\t\t\t\t(default is random value)"
    print "\t--output <output-dir>"
    print "\t-o <output-dir>\t\tuse <output-dir> for storing downloaded data"
    print "\t\t\t\t(default is current directory)"
    print "\t--version"
    print "\t-v\t\t\tprint version and exit"
    print "\t--help"
    print "\t-h\t\t\tprint this help screen"
    print
    print "Report bugs to <" + report_email + ">"

# Print version information
def print_version():
    print version, "<" + report_email + ">"

# Print torrent statistics
def state_callback(ds):
    d = ds.get_download()
#    print >>sys.stderr,`d.get_def().get_name()`,dlstatus_strings[ds.get_status()],ds.get_progress(),"%",ds.get_error(),"up",ds.get_current_speed(UPLOAD),"down",ds.get_current_speed(DOWNLOAD)
    print >>sys.stderr, '%s %s %5.2f%% %s up %8.2fKB/s down %8.2fKB/s' % \
            (d.get_def().get_name(), \
            dlstatus_strings[ds.get_status()], \
            ds.get_progress() * 100, \
            ds.get_error(), \
            ds.get_current_speed(UPLOAD), \
            ds.get_current_speed(DOWNLOAD))

    return (1.0, False)

def main():
    try:
        # opts = a list of (option, value) pairs
        # args = the list of program arguments left after the option list was stripped
        opts, args = getopt.getopt(sys.argv[1:], "hvo:p:", ["help", "version", "output-dir", "port"])
    except getopt.GetoptError, err:
        print str(err)
        usage()
        sys.exit(2)

    # init to default values
    output_dir = os.getcwd()
    port = random.randint(10000, 65535)

    for o, a in opts:
        if o in ("-h", "--help"):
            usage()
            sys.exit(0)
        elif o in ("-o", "--output-dir"):
            output_dir = a
        elif o in ("-p", "--port"):
            port = int(a)
        elif o in ("-v", "--version"):
            print_version()
            sys.exit(0)
        else:
            assert False, "unhandled option"

    if len(args) == 0:
        usage()
        sys.exit(2)

    if len(args) > 1:
        print "Too many arguments"
        usage()
        sys.exit(2)
    torrentfile_or_url = args[0]

    print "Press Ctrl-C to stop the download"

    # setup session
    sscfg = SessionStartupConfig()
    statedir = tempfile.mkdtemp()
    sscfg.set_state_dir(statedir)
    sscfg.set_listen_port(port)
    sscfg.set_megacache(False)
    sscfg.set_overlay(False)
    sscfg.set_dialback(True)
    sscfg.set_internal_tracker(False)
    sscfg.set_dispersy(False)

    s = Session(sscfg)

    # setup and start download
    dscfg = DownloadStartupConfig()
    dscfg.set_dest_dir(output_dir);
    #dscfg.set_max_speed( UPLOAD, 10 )

    # SWIFTPROC
    if torrentfile_or_url.startswith("http") or torrentfile_or_url.startswith(P2PURL_SCHEME):
        cdef = TorrentDef.load_from_url(torrentfile_or_url)
    elif torrentfile_or_url.startswith(SWIFT_URL_SCHEME):
        cdef = SwiftDef.load_from_url(torrentfile_or_url)
    else:
        cdef = TorrentDef.load(torrentfile_or_url)

    if cdef.get_def_type() == "torrent" and cdef.get_live():
        raise ValueError("cmdlinedl does not support live torrents")

    d = s.start_download(cdef, dscfg)
    d.set_state_callback(state_callback, getpeerlist=False)

    #
    # loop while waiting for CTRL-C (or any other signal/interrupt)
    #
    # - cannot use sys.stdin.read() - it means busy waiting when running
    #   the process in background
    # - cannot use condition variable - that don't listen to KeyboardInterrupt
    #
    # time.sleep(sys.maxint) has "issues" on 64bit architectures; divide it
    # by some value (2048) to solve problem
    #
    try:
        while True:
            time.sleep(sys.maxint/2048)
    except:
        print_exc()

    s.shutdown()
    time.sleep(3)
    shutil.rmtree(statedir)


if __name__ == "__main__":
    main()
