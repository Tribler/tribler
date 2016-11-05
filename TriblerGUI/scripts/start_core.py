print "at start of script"

import os
import sys

from twisted.internet import reactor
from twisted.internet.defer import Deferred

sys.path.insert(0, os.environ['base_path'])
sys.path.insert(0, os.path.join(os.environ['base_path'], "tribler_source"))
sys.path.insert(0, os.path.join(os.environ['base_path'], "twisted", "plugins"))

print "here1"

from tribler_plugin import TriblerServiceMaker

sys.stdout = os.fdopen(sys.stdout.fileno(), 'w', 0)
sys.stderr = os.fdopen(sys.stderr.fileno(), 'w', 0)

service = TriblerServiceMaker()
options = {"restapi": 8085, "statedir": None, "dispersy": -1, "libtorrent": -1}

print "here2"

def on_tribler_started(session):
    """
    We print a magic string when Tribler has started. While this solution is not pretty, it is more reliable than
    trying to connect to the events endpoint with an interval.
    """
    print "TRIBLER_STARTED_3894"

start_deferred = Deferred().addCallback(on_tribler_started)

reactor.callWhenRunning(service.start_tribler, options, start_deferred=start_deferred)
reactor.run()
