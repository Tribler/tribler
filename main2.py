import sys
import time

from triblerAPI import *

s = Session()

def states_callback(dslist):
    for ds in dslist:
        d = ds.get_download()
        print >>sys.stderr,"main2: Stats",`d.get_def().get_name()`,dlstatus_strings[ds.get_status()],ds.get_progress(),"%",ds.get_error(),"up",ds.get_current_speed(UPLOAD),"down",ds.get_current_speed(DOWNLOAD),currentThread().getName()

    return (1.0,False)

if __name__ == "__main__":
    
    s.set_download_states_callback(states_callback,getpeerlist=False)
    
    time.sleep(2500)
