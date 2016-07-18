import os
import sys

from twisted.internet import reactor

sys.path.append(os.environ['base_path'])
sys.path.append(os.path.join(os.environ['base_path'], "twisted", "plugins"))

from tribler_plugin import TriblerServiceMaker

service = TriblerServiceMaker()
options = {"restapi": 8085, "statedir": None, "dispersy": -1, "libtorrent": -1}

reactor.callWhenRunning(service.start_tribler, options)
reactor.run()
