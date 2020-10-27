"""
This script enables you to start Tribler headless.
"""
import argparse
import os
import re
import signal
import sys
import time
from asyncio import ensure_future, get_event_loop, sleep
from datetime import date
from socket import inet_aton

from tribler_core.config.tribler_config import TriblerConfig
from tribler_core.modules.process_checker import ProcessChecker
from tribler_core.session import Session
from tribler_core.utilities.osutils import get_appstate_dir
from tribler_core.utilities.path_util import Path


class IPPortAction(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
        parsed = re.match(r"^([\d\.]+)\:(\d+)$", values)
        if not parsed:
            raise argparse.ArgumentError("Invalid address:port")

        ip, port = parsed.group(1), int(parsed.group(2))
        try:
            inet_aton(ip)
        except:
            raise argparse.ArgumentError("Invalid server address")

        if not (0 < port < 65535):
            raise argparse.ArgumentError("Invalid server port")
        setattr(namespace, self.dest, values)


class TriblerService(object):

    def __init__(self):
        """
        Initialize the variables of the TriblerServiceMaker and the logger.
        """
        self.session = None
        self._stopping = False
        self.process_checker = None

    def log_incoming_remote_search(self, sock_addr, keywords):
        d = date.today()
        with open(os.path.join(self.session.config.get_state_dir(), 'incoming-searches-%s' % d.isoformat()),
                  'a') as log_file:
            log_file.write("%s %s %s %s" % (time.time(), sock_addr[0], sock_addr[1], ";".join(keywords)))

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

        statedir = Path(options.statedir or Path(get_appstate_dir(), '.Tribler'))
        config = TriblerConfig(statedir, config_file=statedir / 'triblerd.conf')

        # Check if we are already running a Tribler instance
        self.process_checker = ProcessChecker()
        if self.process_checker.already_running:
            print("Another Tribler instance is already using statedir %s" % config.get_state_dir())
            get_event_loop().stop()
            return

        print("Starting Tribler")

        if options.restapi > 0:
            config.set_api_http_enabled(True)
            config.set_api_http_port(options.restapi)

        if options.ipv8 > 0:
            config.set_ipv8_port(options.ipv8)
        elif options.ipv8 == 0:
            config.set_ipv8_enabled(False)

        if options.libtorrent != -1 and options.libtorrent > 0:
            config.set_libtorrent_port(options.libtorrent)

        if options.ipv8_bootstrap_override is not None:
            config.set_ipv8_bootstrap_override(options.ipv8_bootstrap_override)

        if options.testnet:
            config.set_tunnel_testnet(True)
            config.set_chant_testnet(True)
            config.set_bandwidth_testnet(True)

        self.session = Session(config)
        try:
            await self.session.start()
        except Exception as e:
            print(str(e))
            get_event_loop().stop()
        else:
            print("Tribler started")


def main(argv):
    parser = argparse.ArgumentParser(add_help=False, description=('Tribler script, starts Tribler as a service'))
    parser.add_argument('--help', '-h', action='help', default=argparse.SUPPRESS,
                        help='Show this help message and exit')
    parser.add_argument('--statedir', '-s', default=None, help='Use an alternate statedir')
    parser.add_argument('--restapi', '-p', default=-1, type=int, help='Use an alternate port for REST API')
    parser.add_argument('--ipv8', '-i', default=-1, type=int, help='Use an alternate port for the IPv8')
    parser.add_argument('--libtorrent', '-l', default=-1, type=int, help='Use an alternate port for libtorrent')
    parser.add_argument('--ipv8_bootstrap_override', '-b', default=None, type=str,
                        help='Force the usage of specific IPv8 bootstrap server (ip:port)', action=IPPortAction)

    parser.add_argument('--testnet', '-t', action='store_const', default=False, const=True, help='Join the testnet')

    args = parser.parse_args(sys.argv[1:])
    service = TriblerService()

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
