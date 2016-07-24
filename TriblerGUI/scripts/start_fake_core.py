import logging
import os
import sys

if len(sys.argv) < 2:
    exit()

os.chdir(os.path.join(os.path.dirname(__file__), "..", "..", "Tribler", "Test", "GUI", "FakeApi"))
sys.path.insert(0, os.path.abspath(os.getcwd()))

from twisted.internet import reactor
from twisted.web.server import Site

from endpoints.root_endpoint import RootEndpoint
from tribler_data import TriblerData
import tribler_utils


def generate_tribler_data():
    tribler_utils.tribler_data = TriblerData()
    tribler_utils.tribler_data.generate()

logging.basicConfig()
logger = logging.getLogger(__file__)
logger.setLevel(logging.INFO)

logger.info("Generating random Tribler data")
generate_tribler_data()

site = Site(RootEndpoint())
port = int(sys.argv[1])
logger.info("Starting fake Tribler API on port %d" % port)
reactor.listenTCP(port, site)
reactor.run()
