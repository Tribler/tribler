import sys
import shutil
import time
import tempfile
import random
from traceback import print_exc

from Tribler.Core.API import *

def state_callback(ds):
    d = ds.get_download()
    print >>sys.stderr,`d.get_def().get_name()`,dlstatus_strings[ds.get_status()],ds.get_progress(),"%",ds.get_error(),"up",ds.get_current_speed(UPLOAD),"down",ds.get_current_speed(DOWNLOAD)

    return (1.0,False)

if __name__ == "__main__":

    if sys.argv <= 1:
        print "Usage: cmdlinedl file.torrent [destdir]"
        sys.exit(0)

    print "Press Ctrl-C to stop the download"

    sscfg = SessionStartupConfig()
    statedir = tempfile.mkdtemp()
    sscfg.set_state_dir(statedir)
    sscfg.set_listen_port(random.randint(10000, 60000))
    sscfg.set_megacache(False)
    sscfg.set_overlay(False)
    sscfg.set_dialback(True)
    sscfg.set_internal_tracker(False)
    
    s = Session(sscfg)

    dscfg = DownloadStartupConfig()
    if sys.argv == 3:
        dscfg.set_dest_dir(sys.argv[2])
    else:
        dscfg.set_dest_dir('.')

    tdef = TorrentDef.load(sys.argv[1])
    d = s.start_download(tdef,dscfg)
    d.set_state_callback(state_callback,getpeerlist=False)
   
    # condition variable would be prettier, but that don't listen to 
    # KeyboardInterrupt
    #time.sleep(sys.maxint/2048)
    try:
        while True:
            x = sys.stdin.read()
    except:
        print_exc()
    
    s.shutdown()
    time.sleep(3)    
    shutil.rmtree(statedir)
    