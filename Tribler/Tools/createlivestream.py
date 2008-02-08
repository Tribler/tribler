# Written by Arno Bakker 
# see LICENSE.txt for license information

import sys
import os
import shutil
import time
import tempfile
import random
import urllib2
from traceback import print_exc

from Tribler.Core.API import *

def state_callback(ds):
    d = ds.get_download()
    print >>sys.stderr,`d.get_def().get_name()`,dlstatus_strings[ds.get_status()],ds.get_progress(),"%",ds.get_error(),"up",ds.get_current_speed(UPLOAD),"down",ds.get_current_speed(DOWNLOAD)

    return (1.0,False)

def vod_ready_callback(d,mimetype,stream,filename):
    """ Called by the Session when the content of the Download is ready
     
    Called by Session thread """
    print >>sys.stderr,"main: VOD ready callback called ###########################################################",mimetype


if __name__ == "__main__":

    print sys.argv
    if len(sys.argv) == 3 or len(sys.argv) == 4:
        name = sys.argv[1]
        sourceurl = sys.argv[2]
        if len(sys.argv) == 4:
            destdir = sys.argv[3]
        else:
            destdir = '.'
    else:
        print "Usage: createlivestream name sourceurl [destdir]"
        sys.exit(0)

    print "Press Ctrl-C to stop the download"

    sscfg = SessionStartupConfig()
    statedir = tempfile.mkdtemp()
    sscfg.set_state_dir(statedir)
    sscfg.set_listen_port(7763)
    sscfg.set_megacache(False)
    sscfg.set_overlay(False)
    sscfg.set_dialback(True)
    
    s = Session(sscfg)

    dscfg = DownloadStartupConfig()
    dscfg.set_dest_dir(destdir)

    source = urllib2.urlopen(sourceurl)
    dscfg.set_video_start_callback(vod_ready_callback)
    dscfg.set_mode(DLMODE_NORMAL) # H4xor
    dscfg.set_video_source(source)

    tdef = TorrentDef()
    tdef.create_live(name,(1024*1024/8),"1:00:00")
    tdef.set_tracker(s.get_internal_tracker_url())
    tdef.finalize()
    
    torrentbasename = name+'.tstream'
    torrentfilename = os.path.join(destdir,torrentbasename)
    tdef.save(torrentfilename)

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
    
