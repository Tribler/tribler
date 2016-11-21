import logging


def start_fake_core(port):
    from twisted.internet import reactor
    from twisted.web.server import Site

    from FakeTriblerAPI.endpoints.root_endpoint import RootEndpoint
    from FakeTriblerAPI.tribler_data import TriblerData
    import FakeTriblerAPI.tribler_utils as tribler_utils

    def generate_tribler_data():
        tribler_utils.tribler_data = TriblerData()
        tribler_utils.tribler_data.generate()

    logging.basicConfig()
    logger = logging.getLogger(__file__)
    logger.setLevel(logging.INFO)

    logger.info("Generating random Tribler data")
    generate_tribler_data()

    site = Site(RootEndpoint())
    logger.info("Starting fake Tribler API on port %d", port)
    reactor.listenTCP(port, site)
    reactor.run()
