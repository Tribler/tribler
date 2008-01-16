import sys
import time

from Tribler.Core.Session import *
from Tribler.Core.TorrentDef import *

    
sscfg = SessionStartupConfig()
sscfg.set_listen_port(random.randint(10000, 60000))
sscfg.set_overlay(False)
sscfg.set_buddycast(False)
sscfg.set_start_recommender(False)
sscfg.set_torrent_checking(False)
sscfg.set_superpeer(False)
sscfg.set_dialback(True)
sscfg.set_social_networking(False)
sscfg.set_remote_query(False)
sscfg.set_internal_tracker(False)
sscfg.set_bartercast(False)

s = Session(sscfg)

def states_callback(dslist):
    for ds in dslist:
        d = ds.get_download()
        print >>sys.stderr,"main2: Stats",`d.get_def().get_name()`,dlstatus_strings[ds.get_status()],ds.get_progress(),"%",ds.get_error(),"up",ds.get_current_speed(UPLOAD),"down",ds.get_current_speed(DOWNLOAD),currentThread().getName()

    return (1.0,False)

if __name__ == "__main__":

    if sys.argv <= 1:
        print "Usage: cmdlinedl file.torrent"
        sys.exit(0)
    
    s.set_download_states_callback(states_callback,getpeerlist=False)
    tdef = TorrentDef.load(sys.argv[1])
    
    d = s.start_download(tdef)
   
    time.sleep(2500000)
