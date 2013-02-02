# Written by Arno Bakker 
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

from Tribler.__init__ import LIBRARYNAME
from Tribler.Core.API import *
from Tribler.Core.__init__ import version, report_email


checkpointedwhenseeding = False
sesjun = None

def usage():
    print "Usage: python dirseeder.py [options] directory"
    print "Options:"
    print "\t--port <port>"
    print "\t-p <port>\t\tuse <port> to listen for connections"
    print "\t\t\t\t(default is random value)"
    print "\tdirectory (default is current)"
    print "\t--seeder\t\t\tseeder only"
    print "\t--version"
    print "\t-v\t\t\tprint version and exit"
    print "\t--help"
    print "\t-h\t\t\tprint this help screen"
    print
    print "Report bugs to <" + report_email + ">"

def print_version():
    print version, "<" + report_email + ">"

def states_callback(dslist):
    allseeding = True
    for ds in dslist:
        state_callback(ds)
        if ds.get_status() != DLSTATUS_SEEDING:
            allseeding = False
        
    global checkpointedwhenseeding
    global sesjun
    if len(dslist) > 0 and allseeding and not checkpointedwhenseeding:
        checkpointedwhenseeding = True
        print >>sys.stderr,"All seeding, checkpointing Session to enable quick restart"
        sesjun.checkpoint()
        
    return (1.0, False)

def state_callback(ds):
    d = ds.get_download()
#    print >>sys.stderr,`d.get_def().get_name()`,dlstatus_strings[ds.get_status()],ds.get_progress(),"%",ds.get_error(),"up",ds.get_current_speed(UPLOAD),"down",ds.get_current_speed(DOWNLOAD)
    print >>sys.stderr, '%s %s %5.2f%% %s up %8.2fKB/s down %8.2fKB/s' % \
            (`d.get_def().get_name()`, \
            dlstatus_strings[ds.get_status()], \
            ds.get_progress() * 100, \
            ds.get_error(), \
            ds.get_current_speed(UPLOAD), \
            ds.get_current_speed(DOWNLOAD))

    return (1.0, False)

def main():
    try:
        opts, args = getopt.getopt(sys.argv[1:], "hvp:", ["help", "version", "port", "seeder"])
    except getopt.GetoptError, err:
        print str(err)
        usage()
        sys.exit(2)

    # init to default values
    port = 6969
    tracking  = True
    for o, a in opts:
        if o in ("-h", "--help"):
            usage()
            sys.exit(0)
        elif o in ("-p", "--port"):
            port = int(a)
        elif o in ("-p", "--port"):
            port = int(a)
        elif o in ("--seeder"):
            tracking = False
        elif o in ("-v", "--version"):
            print_version()
            sys.exit(0)
        else:
            assert False, "unhandled option"


    if len(args) > 1:
        print "Too many arguments"
        usage()
        sys.exit(2)
    elif len(args) == 0:
        torrentsdir = os.getcwd()
    else:
        torrentsdir = os.path.abspath(args[0])

    print "Press Ctrl-C or send SIGKILL or WM_DESTROY to stop seeding"

    # setup session
    sscfg = SessionStartupConfig()
    statedir = os.path.join(torrentsdir,"."+LIBRARYNAME)
    sscfg.set_state_dir(statedir)
    sscfg.set_listen_port(port)
    sscfg.set_megacache(False)
    sscfg.set_overlay(False)
    sscfg.set_dialback(False)
    if tracking:
        sscfg.set_internal_tracker(True)
        # M23TRIAL, log full
        logfilename = "tracker-"+str(int(time.time()))+".log"
        sscfg.set_tracker_logfile(logfilename)
        sscfg.set_tracker_log_nat_checks(True)
    
    s = Session(sscfg)
    global sesjun
    sesjun = s
    s.set_download_states_callback(states_callback, getpeerlist=False)
    
    # Restore previous Session
    s.load_checkpoint()

    # setup and start downloads
    dscfg = DownloadStartupConfig()
    dscfg.set_dest_dir(torrentsdir)
    #dscfg.set_max_speed(UPLOAD,256) # FOR DEMO
    
    ##dscfg.set_max_uploads(32)
    
    #
    # Scan dir, until exit by CTRL-C (or any other signal/interrupt)
    #
    try:
        while True:
            try:
                print >>sys.stderr,"Rescanning",`torrentsdir`
                for torrent_file in os.listdir(torrentsdir):
                    if torrent_file.endswith(".torrent") or torrent_file.endswith(".tstream") or torrent_file.endswith(".url"): 
                        print >>sys.stderr,"Found file",`torrent_file`
                        tfullfilename = os.path.join(torrentsdir,torrent_file)
                        if torrent_file.endswith(".url"):
                            f = open(tfullfilename,"rb")
                            url = f.read()
                            f.close()
                            tdef = TorrentDef.load_from_url(url)
                        else:
                            tdef = TorrentDef.load(tfullfilename)
                        
                        # See if already running:
                        dlist = s.get_downloads()
                        existing = False
                        for d in dlist:
                            existinfohash = d.get_def().get_infohash()
                            if existinfohash == tdef.get_infohash():
                                existing = True
                                break
                        if existing:
                            print >>sys.stderr,"Ignoring existing Download",`tdef.get_name()`
                        else:
                            if tracking:
                                s.add_to_internal_tracker(tdef)
#                            d = s.start_download(tdef, dscfg)
                            
                            # Checkpoint again when new are seeding
                            global checkpointedwhenseeding
                            checkpointedwhenseeding = False
                            
            except KeyboardInterrupt,e:
                raise e
            except Exception, e:
                print_exc()
            
            time.sleep(30.0)

    except Exception, e:
        print_exc()

if __name__ == "__main__":
    main()
