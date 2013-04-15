# Written by Njaal Borch
# see LICENSE.txt for license information
#

import sys
import os
import time
import tempfile
import random
import urllib2
import socket # To get fq host name
from base64 import encodestring
from traceback import print_exc
from threading import Condition

from Tribler.Core.API import *
from Tribler.Core.Statistics.Status import *

import Tribler.Core.Utilities.parseargs as parseargs


argsdef = [('nuploads', 200, 'the max number of peers to serve directly'),
           ('destdir', '/tmp/', 'Where to save the downloaded/seeding files')
           ]


def state_callback(ds):
    d = ds.get_download()
    print >>sys.stderr,`d.get_def().get_name()`,dlstatus_strings[ds.get_status()],ds.get_progress(),"%",ds.get_error(),"up",ds.get_current_speed(UPLOAD),"down",ds.get_current_speed(DOWNLOAD)

    return (1.0,False)

def get_usage(defs):
    return parseargs.formatDefinitions(defs,80)


class PrintStatusReporter(Status.OnChangeStatusReporter):
    """
    Print all changes to the screen
    """
    def report(self, event):
        """
        print to screen
        """
        print >> sys.stderr, "STATUS: %s=%s"%(event.get_name(),
                                              event.get_value())


if __name__ == "__main__":

    config, fileargs = parseargs.Utilities.parseargs(sys.argv, argsdef, presets = {})

    if len(sys.argv) < 2:
        raise SystemExit("Missing .torrent or .tstream to seed")

    sscfg = SessionStartupConfig()
    state_dir = Session.get_default_state_dir('.seeder')
    sscfg.set_state_dir(state_dir)
    port = random.randint(10000,20000)
    sscfg.set_listen_port(port)
    sscfg.set_megacache(False)
    sscfg.set_overlay(False)
    sscfg.set_dialback(True)

    s = Session(sscfg)

    print >>sys.stderr,"My permid:",encodestring(s.get_permid()).replace("\n","")

    source = sys.argv[1]
    if source.startswith("http://"):
        tdef = TorrentDef.load_from_url(source)
    else:
        tdef = TorrentDef.load(source)

    poa = None
    if tdef.get_cs_keys():
        try:
            poa = ClosedSwarm.trivial_get_poa(s.get_default_state_dir(),
                                              s.get_permid(),
                                              tdef.infohash)
        except:
            pass # DEBUG ONLY

    dscfg = DownloadStartupConfig()
    dscfg.set_dest_dir(config['destdir'])

    if poa:
        dscfg.set_poa(poa)

    dscfg.set_max_uploads(config['nuploads'])

    print "Press Ctrl-C to stop seeding"

    status = Status.get_status_holder("LivingLab")
    id = "seed_" + socket.getfqdn()

    # Print status updates to the screen
    #status.add_reporter(PrintStatusReporter("Screen"))

    # Report status to the Living lab every 30 minutes
    reporter = LivingLabReporter.LivingLabPeriodicReporter("Living lab CS reporter", 60*30, id, print_post=True)
    status.add_reporter(reporter)


    d = s.start_download(tdef,dscfg)
    d.set_state_callback(state_callback,getpeerlist=[])

    while True:
        try:
            time.sleep(60)
        except:
            break

    #cond = Condition()
    #cond.acquire()
    #cond.wait()
    reporter.stop()

    s.shutdown()
