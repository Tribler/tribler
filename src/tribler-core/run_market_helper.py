"""
This script enables you to start Tribler MarketService headless.
"""
import argparse
import signal
import sys
from asyncio import ensure_future, get_event_loop, sleep

from tribler_core.config.tribler_config import TriblerConfig
from tribler_core.modules.process_checker import ProcessChecker
from tribler_core.session import Session
from tribler_core.utilities.osutils import get_appstate_dir
from tribler_core.utilities.path_util import Path


class MarketService(object):

    def __init__(self):
        self.session = None
        self._stopping = False
        self.process_checker = None
        self.market_community = None

    async def start_tribler(self, options):
        """
        Main method to startup Tribler.
        """
        async def signal_handler(sig):
            print("Received shut down signal %s" % sig)
            if not self._stopping:
                self._stopping = True
                await self.session.shutdown()
                print("Tribler shut down")
                get_event_loop().stop()
                self.process_checker.remove_lock_file()

        signal.signal(signal.SIGINT, lambda sig, _: ensure_future(signal_handler(sig)))
        signal.signal(signal.SIGTERM, lambda sig, _: ensure_future(signal_handler(sig)))

        config = TriblerConfig(options.statedir or Path(get_appstate_dir(), '.Tribler'))
        config.set_torrent_checking_enabled(False)
        config.set_libtorrent_enabled(True)
        config.set_http_api_enabled(True)
        config.set_credit_mining_enabled(False)
        config.set_dummy_wallets_enabled(True)
        config.set_popularity_community_enabled(False)
        config.set_chant_enabled(False)

        # Check if we are already running a Tribler instance
        self.process_checker = ProcessChecker()
        if self.process_checker.already_running:
            print("Another Tribler instance is already using statedir %s" % config.get_state_dir())
            get_event_loop().stop()
            return

        print("Starting Tribler")

        if options.restapi > 0:
            config.set_http_api_enabled(True)
            config.set_http_api_port(options.restapi)

        if options.ipv8 != -1 and options.ipv8 > 0:
            config.set_ipv8_port(options.ipv8)

        if options.testnet:
            config.set_testnet(True)

        self.session = Session(config)
        try:
            await self.session.start()
        except Exception as e:
            print(str(e))
            get_event_loop().stop()
        else:
            print("Tribler started")

def main(argv):
    parser = argparse.ArgumentParser(add_help=False, description=('Run a liteweight Tribler with the Market community'))
    parser.add_argument('--help', '-h', action='help', default=argparse.SUPPRESS, help='Show this help message and exit')
    parser.add_argument('--statedir', '-s', default=None, help='Use an alternate statedir')
    parser.add_argument('--restapi', '-p', default=-1, type=int, help='Use an alternate port for REST API')
    parser.add_argument('--ipv8', '-i', default=8085, type=int, help='Use an alternate port for the IPv8')
    
    parser.add_argument('--testnet', '-t', action='store_const', default=False, const=True, help='Join the testnet')

    args = parser.parse_args(sys.argv[1:])    
    service = MarketService()
    
    loop = get_event_loop()
    coro = service.start_tribler(args)
    ensure_future(coro)
    
    if sys.platform == 'win32':
        # Unfortunately, this is needed on Windows for Ctrl+C to work consistently.
        # Should no longer be needed in Python 3.8.
        async def wakeup():
            while True:
                await sleep(1)
        ensure_future(wakeup())
    
    loop.run_forever()


if __name__ == "__main__":
    main(sys.argv[1:])
