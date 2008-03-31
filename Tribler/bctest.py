import sys
import time

from Tribler.Core.Session import *
from Tribler.Core.TorrentDef import *


def states_callback(dslist):
    for ds in dslist:
        d = ds.get_download()
        print >>sys.stderr,"bctest 1: Stats",`d.get_def().get_name()`,dlstatus_strings[ds.get_status()],ds.get_progress(),"%",ds.get_error(),"up",ds.get_current_speed(UPLOAD),"down",ds.get_current_speed(DOWNLOAD),currentThread().getName()

    return (10.0,False)

if __name__ == "__main__":

    sscfg = SessionStartupConfig()
    sscfg.set_state_dir('Session1')
    sscfg.set_overlay(1)
    sscfg.set_superpeer_file('superpeer1.txt')
    sscfg.set_listen_port(7011)

    s = Session(sscfg)
    s.set_download_states_callback(states_callback,getpeerlist=False)
    tdef = TorrentDef.load('bla.torrent')
    d = s.start_download(tdef)
   
    time.sleep(3600*24*7)
