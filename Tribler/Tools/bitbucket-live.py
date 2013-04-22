import sys
import time
from traceback import print_exc

from Tribler.Core.API import *

DEBUG = False


def vod_event_callback(d,event,params):
    if event == VODEVENT_START:
        stream = params["stream"]

        epoch_server = None
        epoch_local = time.time()
        blocksize = d.get_def().get_piece_length()
        while True:
            stream.read(blocksize)
            last_ts = stream.get_generation_time()

            if epoch_server is None:
                if DEBUG:
                    print >>sys.stderr, "bitbucket: received first data."
                epoch_server = last_ts

            age_server = last_ts - epoch_server
            age_local  = time.time() - epoch_local

            # if server is younger, wait up to sync
            waittime = max( 0, age_server - age_local )
            if DEBUG:
                print >>sys.stderr, "bitbucket: sleeping %.2f seconds. we're at time %.2f, piece has age %.2f" % (waittime,age_local,age_server)
            time.sleep( waittime )


def state_callback(ds):
    try:
        d = ds.get_download()
        p = "%.0f %%" % (100.0*ds.get_progress())
        dl = "dl %.0f" % (ds.get_current_speed(DOWNLOAD))
        ul = "ul %.0f" % (ds.get_current_speed(UPLOAD))
        print >>sys.stderr,dlstatus_strings[ds.get_status() ],p,dl,ul,"====="
    except:
        print_exc()

    return (1.0,False)



scfg = SessionStartupConfig()
scfg.set_megacache( False )
scfg.set_overlay( False )

s = Session( scfg )
tdef = TorrentDef.load(sys.argv[1])
dscfg = DownloadStartupConfig()
dscfg.set_video_event_callback( vod_event_callback )
dscfg.set_max_uploads(16)

d = s.start_download( tdef, dscfg )

d.set_state_callback(state_callback)

while True:
    time.sleep(60)
