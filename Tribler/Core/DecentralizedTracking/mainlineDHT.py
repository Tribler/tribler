# written by Fabian van der Werf, Arno Bakker
# Modified by Raul Jimenez to integrate KTH DHT
# see LICENSE.txt for license information

import sys
import logging
from traceback import print_exc

DEBUG = False
dht_imported = False

if sys.version.split()[0] >= '2.5':
    try:
        import Tribler.Core.DecentralizedTracking.pymdht.core.pymdht as pymdht
        import Tribler.Core.DecentralizedTracking.pymdht.plugins.routing_nice_rtt as routing_mod
        import Tribler.Core.DecentralizedTracking.pymdht.plugins.lookup_a16 as lookup_mod
        dht_imported = True
    except (ImportError), e:
        print_exc()

dht = None

def init(addr, conf_path):
    global dht
    global dht_imported
    
    if DEBUG:
        print >>sys.stderr,'dht: DHT initialization', dht_imported
        log_level = logging.DEBUG
    else:
        log_level = logging.ERROR
    if dht_imported and dht is None:
        private_dht_name = None
        dht = pymdht.Pymdht(addr, conf_path, routing_mod, lookup_mod,
                            private_dht_name, log_level)
        if DEBUG:
            print >>sys.stderr,'dht: DHT running'

def control():
    import pdb
    pdb.set_trace()

def deinit():
    global dht
    if dht is not None:
        try:
            dht.stop()
        except:
            pass
