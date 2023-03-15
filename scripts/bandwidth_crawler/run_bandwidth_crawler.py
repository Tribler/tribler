"""
This executable script starts a Tribler instance and joins the BandwidthAccountingCommunity.
"""
import argparse
import logging
import signal
import sys
from asyncio import ensure_future, get_event_loop
from pathlib import Path

from tribler.core.components.bandwidth_accounting.bandwidth_accounting_component import BandwidthAccountingComponent
from tribler.core.components.ipv8.ipv8_component import Ipv8Component
from tribler.core.components.key.key_component import KeyComponent
from tribler.core.components.session import Session
from tribler.core.config.tribler_config import TriblerConfig
from tribler.core.utilities.utilities import make_async_loop_fragile


class PortAction(argparse.Action):
    def __call__(self, _, namespace, value, option_string=None):
        if not 0 < value < 2 ** 16:
            raise argparse.ArgumentError(self, "Invalid port number")
        setattr(namespace, self.dest, value)


async def crawler_session(session_config: TriblerConfig):
    session = Session(session_config,
                      [KeyComponent(), Ipv8Component(), BandwidthAccountingComponent(crawler_mode=True)])
    signal.signal(signal.SIGTERM, lambda signum, stack: session.shutdown_event.set)
    async with session:
        await session.shutdown_event.wait()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=('Start a crawler in the bandwidth accounting community'))
    parser.add_argument('--statedir', '-s', default='bw_crawler', type=str, help='Use an alternate statedir')
    parser.add_argument('--restapi', '-p', default=20100, type=int, help='Use an alternate port for the REST API',
                        action=PortAction, metavar='{0..65535}')
    parser.add_argument('--fragile', '-f', help='Fail at the first error', action='store_true')
    args = parser.parse_args(sys.argv[1:])

    logging.basicConfig(level=logging.INFO)

    state_dir = Path(args.statedir).absolute()
    config = TriblerConfig.load(state_dir=state_dir)

    config.tunnel_community.enabled = False
    config.libtorrent.enabled = False
    config.bootstrap.enabled = False
    config.chant.enabled = False
    config.torrent_checking.enabled = False
    config.api.http_enabled = True
    config.api.http_port = args.restapi
    config.bandwidth_accounting.outgoing_query_interval = 5

    loop = get_event_loop()
    if args.fragile:
        make_async_loop_fragile(loop)
    ensure_future(crawler_session(config))
    loop.run_forever()
