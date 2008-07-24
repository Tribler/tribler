import sys
import time
from Tribler.Core.Session import Session
from Tribler.Core.SessionConfig import SessionStartupConfig
from Tribler.Core.TorrentDef import TorrentDef
from Tribler.Core.DownloadConfig import DownloadStartupConfig

DEBUG = True


def vod_event_callback(d,event,params):
    if event == "start":
        stream = params["stream"]

        epoch_server = None
        epoch_local = time.time()
        while True:
            stream.read()
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


scfg = SessionStartupConfig()
scfg.set_overlay( False )

s = Session( scfg )
tdef = TorrentDef.load('ParadisoCam.mpegts.tstream')
dscfg = DownloadStartupConfig()
dscfg.set_video_event_callback( vod_event_callback )

d = s.start_download( tdef, dscfg )

while True:
  time.sleep(60)

