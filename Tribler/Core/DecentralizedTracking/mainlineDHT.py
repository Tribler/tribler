# written by Fabian van der Werf, Arno Bakker
# Modified by Raul Jimenez to integrate KTH DHT
# see LICENSE.txt for license information

import sys
import logging
from traceback import print_exc

DEBUG = False
dht_imported = False

SWIFT_PORT = 9999

if sys.version.split()[0] >= '2.5':
    try:
        import Tribler.Core.DecentralizedTracking.pymdht.core.pymdht as pymdht
        import Tribler.Core.DecentralizedTracking.pymdht.core.node as node
        import Tribler.Core.DecentralizedTracking.pymdht.plugins.routing_nice_rtt as routing_mod
        import Tribler.Core.DecentralizedTracking.pymdht.plugins.lookup_a4 as lookup_mod
        import Tribler.Core.DecentralizedTracking.pymdht.core.exp_plugin_template as experimental_m_mod
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
        my_node = node.Node(addr, None, version=pymdht.VERSION_LABEL)
        private_dht_name = None
        dht = pymdht.Pymdht(my_node, conf_path,
                            routing_mod,
                            lookup_mod,
                            experimental_m_mod,
                            private_dht_name,
                            log_level,
                            swift_port=SWIFT_PORT)
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
