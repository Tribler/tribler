# written by Fabian van der Werf, Arno Bakker
# Modified by Raul Jimenez to integrate KTH DHT
# see LICENSE.txt for license information

import sys
import logging

logger = logging.getLogger(__name__)

DEBUG = False

DHT_IMPORTED = False
try:
    import Tribler.Core.DecentralizedTracking.pymdht.core.pymdht as pymdht
    import Tribler.Core.DecentralizedTracking.pymdht.core.node as node
    import Tribler.Core.DecentralizedTracking.pymdht.plugins.routing_nice_rtt as routing_mod
    import Tribler.Core.DecentralizedTracking.pymdht.plugins.lookup_a4 as lookup_mod
    import Tribler.Core.DecentralizedTracking.pymdht.core.exp_plugin_template as experimental_m_mod
    DHT_IMPORTED = True
except ImportError:
    logger.exception(u"Could not import pymdht")


def init(addr, conf_path):
    if DEBUG:
        log_level = logging.DEBUG
    else:
        log_level = logging.ERROR
    logger.debug(u"DHT initialization %s", DHT_IMPORTED)

    if DHT_IMPORTED:
        my_node = node.Node(addr, None, version=pymdht.VERSION_LABEL)
        private_dht_name = None
        dht = pymdht.Pymdht(my_node, conf_path,
                            routing_mod,
                            lookup_mod,
                            experimental_m_mod,
                            private_dht_name,
                            log_level)
        logger.debug(u"DHT running")
        return dht


def deinit(dht):
    if dht is not None:
        try:
            dht.stop()
        except:
            logger.exception(u"could not stop DHT")
