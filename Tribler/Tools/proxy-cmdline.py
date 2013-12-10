# Written by Arno Bakker, George Milescu
# see LICENSE.txt for license information
#
# Razvan Deaconescu, 2008:
#       * corrected problem when running in background
#       * added usage and print_version functions
#       * uses getopt for command line argument parsing
# George Milescu, 2009
#       * Added arguments for doemode

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
from Tribler.Core.Utilities.utilities import show_permid_short
from M2Crypto import EC

# Print usage message


def usage():
    print "Usage: python proxy-cmdlinedl.py [options] torrent_file"
    print "Options:"
    print "\t--port <port>"
    print "\t-p <port>\t\tuse <port> to listen for connections"
    print "\t\t\t\t(default is random value)"
    print "\t--output <output-dir>"
    print "\t-o <output-dir>\t\tuse <output-dir> for storing downloaded data"
    print "\t\t\t\t(default is current directory)"
    print "\t--state-dir <state-dir>"
    print "\t\t\t\tuse <state-dir> for storing session data"
    print "\t\t\t\t(default is /tmp/tmp-tribler)"
    print "\t--doemode <doe-mode>"
    print "\t\t\t\t[DEVEL] use <doe-mode> to specify how the client behaves"
    print "\t\t\t\t * doe-mode = off: no proxy is being used (the client is either an helper, or it does not start use proxy connections)"
    print "\t\t\t\t * doe-mode = private: only proxy connections are being used"
    print "\t\t\t\t * doe-mode = speed: both proxy and direct connections are being used"
    print "\t\t\t\t(default is off)"
    print "\t--proxyservice <proxy-service>"
    print "\t\t\t\t[DEVEL] use <proxy-mode> to specify how the client behaves"
    print "\t\t\t\t * proxy-service = off: the current node can not be used as a proxy by other nodes"
    print "\t\t\t\t * proxy-service = on: the current node can be used as a proxy by other nodes"
    print "\t\t\t\t(default is off)"
    print "\t--helpers <helpers>"
    print "\t\t\t\t[DEVEL] use <helpers> to specify maximum number of helpers used or a torrent"
    print "\t\t\t\t(default is 5)"
    print "\t--test-mode <test-mode>"
    print "\t\t\t\t[DEVEL] use <test-mode> to specify if the client runs as part of a test"
    print "\t\t\t\t * test-mode = off: the client is not run as part of a test"
    print "\t\t\t\t * test-mode = doe: the client is part of a test, as a coordinator"
    print "\t\t\t\t * test-mode = proxy: the client is part of a test, as a helper"
    print "\t\t\t\t(default is off)"
    print "\t--no-download"
    print "\t\t\t\t[DEVEL] Don't download anything, just stay and wait"
    print "\t\t\t\t(if not present the default to download the torrent data)"
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
        (d.get_def().get_name(),
            dlstatus_strings[ds.get_status()],
            ds.get_progress() * 100,
            ds.get_error(),
            ds.get_current_speed(UPLOAD),
            ds.get_current_speed(DOWNLOAD))

    return (1.0, False)


def main():
    try:
        # opts = a list of (option, value) pairs
        # args = the list of program arguments left after the option list was stripped
        opts, args = getopt.getopt(sys.argv[1:], "hvo:p:", ["help", "version", "output-dir=", "port=", "doemode=", "proxyservice=", "proxies=", "test-mode=", "state-dir=", "no-download"])
    except getopt.GetoptError as err:
        print str(err)
        usage()
        sys.exit(2)

    # init the default values
    output_dir = os.getcwd()
    port = random.randint(10000, 65535)
    id = None
    doe_mode = DOE_MODE_OFF
    proxy_service = PROXYSERVICE_OFF
    proxies = 5
    test_mode = "off"  # off, doe, proxy
    no_download = False
    statedir = "/tmp/tmp-tribler"

    # get values from arguments
    for option, value in opts:
        if option in ("-h", "--help"):
            usage()
            sys.exit(0)
        elif option in ("-o", "--output-dir"):
            output_dir = value
        elif option in ("--state-dir"):
            statedir = value
        elif option in ("-p", "--port"):
            port = int(value)
        elif option in ("--doemode"):
            if value == "off":
                doe_mode = DOE_MODE_OFF
            elif value == "private":
                doe_mode = DOE_MODE_PRIVATE
            elif value == "speed":
                doe_mode = DOE_MODE_SPEED
            else:
                doe_mode = DOE_MODE_OFF
        elif option in ("--proxyservice"):
            if value == "off":
                proxy_service = PROXYSERVICE_OFF
            elif value == "on":
                proxy_service = PROXYSERVICE_ON
            else:
                proxy_service = PROXYSERVICE_OFF
        elif option in ("--proxies"):
            proxies = int(value)
        elif option in ("--test-mode"):
            test_mode = value
        elif option in ("-v", "--version"):
            print_version()
            sys.exit(0)
        elif option in ("--no-download"):
            no_download = True
        else:
            assert False, "unhandled option"

    # arg should have only one element left: the torrent file name
    # ProxyDevel
    # if no_download is false (the client has to download torrent data), check number of arguments
    if (no_download == False) and len(args) == 0:
        usage()
        sys.exit(2)
    if len(args) > 1:
        print "Too many arguments"
        usage()
        sys.exit(2)

    # ProxyDevel
    # is no_download is false (the client has to download torrent data), get torrent file name
    if (no_download == False):
        torrent_file = args[0]

    print "Press Ctrl-C to stop the download"

    # session setup
    session_startup_config = SessionStartupConfig()
    # statedir = tempfile.mkdtemp()
    # ProxyDevel - set custom state dir
    session_startup_config.set_state_dir(statedir)
    session_startup_config.set_proxyservice_dir(os.path.join(statedir, "proxyservice"))
    session_startup_config.set_listen_port(port)
    session_startup_config.set_megacache(True)
    session_startup_config.set_overlay(True)
    session_startup_config.set_dialback(True)
    session_startup_config.set_internal_tracker(False)
    session_startup_config.set_dispersy(True)
    # ProxyDevel - turn DHT off
    # session_startup_config.set_mainline_dht(False)
    # ProxyDevel - turn buddycast off
    # session_startup_config.set_buddycast(False)
    # ProxyDevel - set new core API values
    session_startup_config.set_proxyservice_status(proxy_service)

    s = Session(session_startup_config)

    # DEBUG
    print "*** My Permid = ", show_permid_short(s.get_permid())

    # ProxyDevel - Receive overlay messages from anyone
    s.set_overlay_request_policy(AllowAllRequestPolicy())

    if test_mode == "doe":
        # add the helper 1 as a friend
        # get helper1 permid
        helper1_keypair_filename = os.path.join("../../P2P-Testing-Infrastructure/ClientWorkingFolders/Proxy01/statedir", "ec.pem")
        helper1_keypair = EC.load_key(helper1_keypair_filename)
        helper1_permid = str(helper1_keypair.pub().get_der())
        # set helper1 ip address
#        helper1_ip="10.10.3.1"
        helper1_ip = "141.85.224.202"
        # set helper1 port
        helper1_port = 25123
        # add helper1 as a peer
        peerdb = s.open_dbhandler(NTFY_PEERS)
        peer = {}
        peer['permid'] = helper1_permid
        peer['ip'] = helper1_ip
        peer['port'] = helper1_port
        peer['last_seen'] = 0
        peerdb.addPeer(peer['permid'], peer, update_dns=True)

        # add the helper 2 as a friend
        # get helper2 permid
        helper2_keypair_filename = os.path.join("../../P2P-Testing-Infrastructure/ClientWorkingFolders/Proxy02/statedir", "ec.pem")
        helper2_keypair = EC.load_key(helper2_keypair_filename)
        helper2_permid = str(helper2_keypair.pub().get_der())
        # set helper2 ip address
#        helper2_ip="10.10.4.1"
        helper2_ip = "141.85.224.203"
        # set helper2 port
        helper2_port = 25123
        # add helper2 as a peer
        peerdb = s.open_dbhandler(NTFY_PEERS)
        peer = {}
        peer['permid'] = helper2_permid
        peer['ip'] = helper2_ip
        peer['port'] = helper2_port
        peer['last_seen'] = 0
        peerdb.addPeer(peer['permid'], peer, update_dns=True)

        # add the helper 3 as a friend
        # get helper3 permid
        helper3_keypair_filename = os.path.join("../../P2P-Testing-Infrastructure/ClientWorkingFolders/Proxy03/statedir", "ec.pem")
        helper3_keypair = EC.load_key(helper3_keypair_filename)
        helper3_permid = str(helper3_keypair.pub().get_der())
        # set helper3 ip address
        helper3_ip = "141.85.224.204"
        # set helper3 port
        helper3_port = 25123
        # add helper3 as a peer
        peerdb = s.open_dbhandler(NTFY_PEERS)
        peer = {}
        peer['permid'] = helper3_permid
        peer['ip'] = helper3_ip
        peer['port'] = helper3_port
        peer['last_seen'] = 0
        peerdb.addPeer(peer['permid'], peer, update_dns=True)

        # add the helper 4 as a friend
        # get helper4 permid
        helper4_keypair_filename = os.path.join("../../P2P-Testing-Infrastructure/ClientWorkingFolders/Proxy04/statedir", "ec.pem")
        helper4_keypair = EC.load_key(helper4_keypair_filename)
        helper4_permid = str(helper4_keypair.pub().get_der())
        # set helper4 ip address
        helper4_ip = "141.85.224.205"
        # set helper4 port
        helper4_port = 25123
        # add helper4 as a peer
        peerdb = s.open_dbhandler(NTFY_PEERS)
        peer = {}
        peer['permid'] = helper4_permid
        peer['ip'] = helper4_ip
        peer['port'] = helper4_port
        peer['last_seen'] = 0
        peerdb.addPeer(peer['permid'], peer, update_dns=True)

    # ProxyDevel - if no_download is false (the client has to download torrent data), then start downloading
    if (no_download == False):
        if test_mode == "doe":
            # setup and start download
            download_startup_config = DownloadStartupConfig()
            download_startup_config.set_dest_dir(output_dir)
            # ProxyDevel - turn PEX off
            # download_startup_config.set_ut_pex_max_addrs_from_peer(0)
            download_startup_config.set_doe_mode(doe_mode)
            download_startup_config.set_proxyservice_role(PROXYSERVICE_ROLE_DOE)
            download_startup_config.set_no_proxies(proxies)

            torrent_def = TorrentDef.load(torrent_file)

            d = s.start_download(torrent_def, download_startup_config)
            d.set_state_callback(state_callback, getpeerlist=[])
        else:
            # setup and start download
            download_startup_config = DownloadStartupConfig()
            download_startup_config.set_dest_dir(output_dir)

            torrent_def = TorrentDef.load(torrent_file)

            d = s.start_download(torrent_def, download_startup_config)
            d.set_state_callback(state_callback, getpeerlist=[])

        # if the client is a coordinator
        if test_mode == "doe":
            # allow time for the download to start, before starting the help request
            time.sleep(3)
            # ask peer for help
            for download in s.get_downloads():
                peerlist = []
                peerlist.append(helper1_permid)
                peerlist.append(helper2_permid)
                peerlist.append(helper3_permid)
                peerlist.append(helper4_permid)
                # download.sd.dow.proxydownloader.doe.send_relay_request(peerlist)

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
    # ProxyDevel
    # shutil.rmtree(statedir)

if __name__ == "__main__":
    main()
