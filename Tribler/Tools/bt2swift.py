# Written by Arno Bakker, Razvan Deaconescu, George Milescu
# see LICENSE.txt for license information
#

import sys
import shutil
import time
import tempfile
import random
import os
import getopt
from traceback import print_exc
from threading import Condition

from Tribler.Core.API import *
from Tribler.Core.__init__ import version, report_email

STATUS_REPORT_INTERVAL = 3.0


cond = Condition()

# Print usage message


def usage():
    print("Usage: python cmdlinedl.py [options] torrentfile_or_url")
    print("Options:")
    print("\t--port <port>")
    print("\t-p <port>\t\tuse <port> to listen for connections")
    print("\t\t\t\t(default is random value)")
    print("\t--output <output-dir>")
    print("\t-o <output-dir>\t\tuse <output-dir> for storing downloaded data")
    print("\t\t\t\t(default is current directory)")
    print("\t--version")
    print("\t-v\t\t\tprint version and exit")
    print("\t--help")
    print("\t-h\t\t\tprint this help screen")
    print()
    print("Report bugs to <" + report_email + ">")

# Print version information


def print_version():
    print(version, "<" + report_email + ">")


def states_callback(dslist):
    for ds in dslist:
        state_callback(ds)
    return (STATUS_REPORT_INTERVAL, False)

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

    if ds.get_status() == DLSTATUS_SEEDING:
        global cond
        cond.acquire()
        cond.notify()
        cond.release()

    return (STATUS_REPORT_INTERVAL, False)


def url2cdef(torrentfile_or_url):
    # SWIFTPROC
    if torrentfile_or_url.startswith("http") or torrentfile_or_url.startswith(P2PURL_SCHEME):
        cdef = TorrentDef.load_from_url(torrentfile_or_url)
    elif torrentfile_or_url.startswith(SWIFT_URL_SCHEME):
        cdef = SwiftDef.load_from_url(torrentfile_or_url)
    else:
        cdef = TorrentDef.load(torrentfile_or_url)

    if cdef.get_def_type() == "torrent" and cdef.get_live():
        raise ValueError("cmdlinedl does not support live torrents")

    return cdef


def start_download(s, cdef, output_dir, listenport):
    # setup and start download
    dscfg = DownloadStartupConfig()
    dscfg.set_dest_dir(output_dir);
    dscfg.set_swift_listen_port(listenport)
    # dscfg.set_max_speed( UPLOAD, 10 )
    # dscfg.set_max_speed( DOWNLOAD, 512 )

    d = s.start_download(cdef, dscfg)
    d.set_state_callback(state_callback, getpeerlist=[])
    return d


def main():
    try:
        # opts = a list of (option, value) pairs
        # args = the list of program arguments left after the option list was stripped
        opts, args = getopt.getopt(sys.argv[1:], "hvo:p:", ["help", "version", "output-dir", "port"])
    except getopt.GetoptError as err:
        print(str(err))
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
        print("Too many arguments")
        usage()
        sys.exit(2)
    torrentfile_or_url = args[0]

    print("Press Ctrl-C to stop the download")

    # setup session
    sscfg = SessionStartupConfig()
    statedir = tempfile.mkdtemp()
    # statedir = '.test' # FOR CHECKPOINT TESTING
    sscfg.set_state_dir(statedir)
    sscfg.set_listen_port(port)
    sscfg.set_megacache(False)
    sscfg.set_swift_path(".\\Tribler\\SwiftEngine\\swift.exe")

    s = Session(sscfg)

    # url = "http://www.vodo.net/media/torrents/Exhibit.A.2007.SD.x264-VODO.torrent"
    url = "http://torrent.fedoraproject.org/torrents/Fedora-20-i386-DVD.torrent"
    tdef = url2cdef(url)

    output_dir = 'D:\\Build\\bt2swift-m48stb-r25811\\orig'
    td = start_download(s, tdef, output_dir, None)

    # Wait till seeding
    print("python: Waiting till BT download is seeding...", file=sys.stderr)
    global cond
    cond.acquire()
    cond.wait()
    cond.release()
    print("python: Reseeding BT via swift", file=sys.stderr)

    sdef = SwiftDef()
    sdef.set_tracker("127.0.0.1:23000")  # set DownloadConfig.set_swift_listen_port() for local tracking
    iotuples = td.get_dest_files()
    for i, o in iotuples:
        print("python: add_content", i, o, file=sys.stderr)
        if len(iotuples) == 1:
            sdef.add_content(o)  # single file .torrent
        else:
            xi = os.path.join(tdef.get_name_as_unicode(), i)
            if sys.platform == "win32":
                xi = xi.replace("\\", "/")
            si = xi.encode("UTF-8")  # spec format
            sdef.add_content(o, si)  # multi-file .torrent

    sdef.finalize(sscfg.get_swift_path(), destdir=output_dir)

    if len(iotuples) == 1:
        storagepath = iotuples[0][1]  # Point to file on disk
    else:
        # Store multi-file spec as <roothashhex> alongside files
        mfpath = os.path.join(output_dir, "." + sdef.get_roothash_as_hex())
        sdef.save_multifilespec(mfpath)
        storagepath = mfpath  # Point to spec file

    sd = start_download(s, sdef, storagepath, 23000)

    time.sleep(3600)

    s.shutdown()
    time.sleep(30)
    # shutil.rmtree(statedir)


if __name__ == "__main__":
    main()
