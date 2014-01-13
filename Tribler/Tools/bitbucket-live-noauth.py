import sys
import time
import random
import tempfile
from traceback import print_exc
from base64 import encodestring

from Tribler.Core.API import *
from Tribler.Core.Utilities.timeouturlopen import urlOpenTimeout

DEBUG = True

RATE = 32768


def vod_event_callback(d, event, params):
    if event == VODEVENT_START:
        stream = params["stream"]

        # SWIFTPROC
        if stream is None:
            # Access swift HTTP interface directly
            stream = urlOpenTimeout(params["url"], timeout=30)
            # ARNOSMPTODO: available()

        grandtotal = 0
        st = time.time()
        while True:
            global RATE
            total = 0
            while total < int(RATE):
                data = stream.read(int(RATE))
                total += len(data)

            grandtotal += total
            et = time.time()
            diff = max(et - st, 0.00001)
            grandrate = float(grandtotal) / diff
            print("bitbucket: grandrate", grandrate, "~", RATE, file=sys.stderr)  # ,"avail",stream.available()
            time.sleep(1.0)


def state_callback(ds):
    try:
        d = ds.get_download()
        p = "%.0f %%" % (100.0 * ds.get_progress())
        dl = "dl %.0f" % (ds.get_current_speed(DOWNLOAD))
        ul = "ul %.0f" % (ds.get_current_speed(UPLOAD))
        print(dlstatus_strings[ds.get_status()], p, dl, ul, "=====", file=sys.stderr)
    except:
        print_exc()

    return (1.0, False)


print("Loading", sys.argv)
statedir = tempfile.mkdtemp()
port = random.randint(10000, 20000)

scfg = SessionStartupConfig()
scfg.set_state_dir(statedir)
scfg.set_listen_port(port)
scfg.set_megacache(False)


s = Session(scfg)

url = sys.argv[1]

# SWIFTPROC
if url.startswith("http") or url.startswith(P2PURL_SCHEME):
    cdef = TorrentDef.load_from_url(url)
    RATE = cdef.get_bitrate()
else:
    cdef = SwiftDef.load_from_url(url)

dscfg = DownloadStartupConfig()
dscfg.set_video_event_callback(vod_event_callback)

# A Closed swarm - load the POA. Will throw an exception if no POA is available
if cdef.get_def_type() == "torrent" and cdef.get_cs_keys():
    print("Is a closed swarm, reading POA", file=sys.stderr)
    try:
        poa = ClosedSwarm.trivial_get_poa(s.get_default_state_dir(),
                                          s.get_permid(),
                                          cdef.get_infohash())
    except Exception as e:
        print("Failed to load POA for swarm", encodestring(cdef.get_infohash()).replace("\n", ""), "from", s.get_default_state_dir(), "(my permid is %s)" % encodestring(s.get_permid()).replace("\n", ""), "Error was:", e, file=sys.stderr)
        raise SystemExit("Failed to load POA, aborting")

d = s.start_download(cdef, dscfg)

d.set_state_callback(state_callback)

while True:
    time.sleep(60)
