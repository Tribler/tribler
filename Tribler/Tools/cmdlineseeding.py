# Written by Arno Bakker
# Modified by Niels Zeilemaker
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
    print("Usage: python cmdlineseeding.py [options] file")
    print("Options:")
    print("\t--port <port>")
    print("\t-p <port>\t\tuse <port> to listen for connections")
    print("\t\t\t\t(default is random value)")
    print("\t--type <type>")
    print("\t-t <type>\t\tdefine type to start seeding")
    print("\t\t\t\t(can be either swift or bittorrent)")
    print("\t--version")
    print("\t-v\t\t\tprint version and exit")
    print("\t--help")
    print("\t-h\t\t\tprint this help screen")
    print()
    print("Example:")
    print("\t python cmdlineseeding.py --port=20000 --type=swift ffmpeg.exe")
    print()
    print("Report bugs to <" + report_email + ">")

# Print version information


def print_version():
    print(version, "<" + report_email + ">")

# Print torrent statistics


def state_callback(ds):
    d = ds.get_download()
#    print >>sys.stderr,`d.get_def().get_name()`,dlstatus_strings[ds.get_status()],ds.get_progress(),"%",ds.get_error(),"up",ds.get_current_speed(UPLOAD),"down",ds.get_current_speed(DOWNLOAD)
    print('%s %s %5.2f%% %s up %8.2fKB/s down %8.2fKB/s' % \
        (d.get_def().get_name(),
            dlstatus_strings[ds.get_status()],
            ds.get_progress() * 100,
            ds.get_error(),
            ds.get_current_speed(UPLOAD),
            ds.get_current_speed(DOWNLOAD)), file=sys.stderr)

    return (1.0, False)


def main():
    try:
        # opts = a list of (option, value) pairs
        # args = the list of program arguments left after the option list was stripped
        opts, args = getopt.getopt(sys.argv[1:], "hvt:p:", ["help", "version", "type=", "port="])
    except getopt.GetoptError as err:
        print(str(err))
        usage()
        sys.exit(2)

    # init to default values
    port = random.randint(10000, 65535)
    seedertype = "swift"
    for o, a in opts:
        if o in ("-h", "--help"):
            usage()
            sys.exit(0)
        elif o in ("-p", "--port"):
            port = int(a)
        elif o in ("-t", "--type"):
            seedertype = a
        elif o in ("-v", "--version"):
            print_version()
            sys.exit(0)
        else:
            assert False, "unhandled option"

    if len(args) == 0:
        usage()
        sys.exit(2)

    if len(args) > 1:
        print("Too many arguments")
        usage()
        sys.exit(2)

    assert os.path.isfile(args[0])
    filename = os.path.abspath(args[0])
    destdir = os.path.dirname(filename)


    print("Press Ctrl-C to stop the download")

    # setup session
    sscfg = SessionStartupConfig()
    statedir = tempfile.mkdtemp()
    sscfg.set_state_dir(statedir)
    sscfg.set_listen_port(port)
    sscfg.set_swift_tunnel_listen_port(port)
    sscfg.set_megacache(False)
    sscfg.set_dispersy(False)

    sscfg.set_swift_proc(seedertype == "swift")
    sscfg.set_libtorrent(seedertype == "bittorrent")

    s = Session(sscfg)
    s.start()

    if seedertype == "swift":
        sdef = SwiftDef()
        sdef.set_tracker("127.0.0.1:%d" % s.get_swift_dht_listen_port())
        sdef.add_content(filename)

        sdef.finalize(s.get_swift_path(), destdir=destdir)

        dscfg = DownloadStartupConfig()
        dscfg.set_dest_dir(filename)
        dscfg.set_swift_meta_dir(destdir)

        cdef = sdef
    else:
        raise NotImplementedError()

    d = s.start_download(cdef, dscfg)
    d.set_state_callback(state_callback, getpeerlist=[])

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
            time.sleep(sys.maxsize / 2048)
    except:
        print_exc()

    s.shutdown()
    time.sleep(3)
    shutil.rmtree(statedir)


if __name__ == "__main__":
    main()
