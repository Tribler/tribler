import logging
import sys
from asyncio import new_event_loop, set_event_loop

from aiohttp import web

from tribler_gui.tests.fake_tribler_api.endpoints.root_endpoint import RootEndpoint
from tribler_gui.tests.fake_tribler_api.tribler_data import TriblerData
import tribler_gui.tests.fake_tribler_api.tribler_utils as tribler_utils

if __name__ == "__main__":
    logging.basicConfig()
    logger = logging.getLogger(__file__)
    logger.setLevel(logging.INFO)

    logger.info("Generating random Tribler data")
    tribler_utils.tribler_data = TriblerData()
    tribler_utils.tribler_data.generate()

    root_endpoint = RootEndpoint(None)
    runner = web.AppRunner(root_endpoint.app)

    loop = new_event_loop()
    set_event_loop(loop)

    api_port = int(sys.argv[1])
    loop.run_until_complete(runner.setup())
    logger.info("Starting fake Tribler API on port %d", api_port)
    site = web.TCPSite(runner, 'localhost', api_port)
    loop.run_until_complete(site.start())
    loop.run_forever()
