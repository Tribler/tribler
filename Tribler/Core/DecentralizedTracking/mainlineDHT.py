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
        import Tribler.Core.DecentralizedTracking.pymdht.core.node as node
        import Tribler.Core.DecentralizedTracking.pymdht.plugins.routing_nice_rtt as routing_mod
        import Tribler.Core.DecentralizedTracking.pymdht.plugins.lookup_a4 as lookup_mod
        import Tribler.Core.DecentralizedTracking.pymdht.core.exp_plugin_template as experimental_m_mod
        dht_imported = True
    except (ImportError) as e:
        print_exc()

def init(addr, conf_path, swift_port):
    global dht_imported
    if DEBUG:
        print('dht: DHT initialization', dht_imported, file=sys.stderr)
        log_level = logging.DEBUG
    else:
        log_level = logging.ERROR

    if dht_imported:
        my_node = node.Node(addr, None, version=pymdht.VERSION_LABEL)
        private_dht_name = None
        dht = pymdht.Pymdht(my_node, conf_path,
                            routing_mod,
                            lookup_mod,
                            experimental_m_mod,
                            private_dht_name,
                            log_level,
                            swift_port=swift_port)
        if DEBUG:
            print('dht: DHT running', file=sys.stderr)
    return dht


def control():
    import pdb
    pdb.set_trace()

def deinit(dht):
    if dht is not None:
        try:
            dht.stop()
        except:
            pass
