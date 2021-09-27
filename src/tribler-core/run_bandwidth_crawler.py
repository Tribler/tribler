"""
This executable script starts a Tribler instance and joins the BandwidthAccountingCommunity.
"""
import argparse
import sys
from asyncio import ensure_future, get_event_loop
from pathlib import Path

from ipv8.loader import IPv8CommunityLoader

from tribler_common.simpledefs import STATEDIR_DB_DIR
from tribler_core.config.tribler_config import TriblerConfig
from tribler_core.components.bandwidth_accounting.db.database import BandwidthDatabase
from tribler_core.modules.bandwidth_accounting.launcher import BandwidthCommunityLauncher
from tribler_core.components.bandwidth_accounting.settings import BandwidthAccountingSettings
from tribler_core.start_core import Session


class PortAction(argparse.Action):
    def __call__(self, _, namespace, values, option_string=None):
        if not 0 < values < 2**16:
            raise argparse.ArgumentError(self, "Invalid port number")
        setattr(namespace, self.dest, values)


class BandwidthCommunityCrawlerLauncher(BandwidthCommunityLauncher):

    def get_kwargs(self, session):
        settings = BandwidthAccountingSettings()
        settings.outgoing_query_interval = 5
        database = BandwidthDatabase(session.config.state_dir / STATEDIR_DB_DIR / "bandwidth.db",
                                     session.trustchain_keypair.pub().key_to_bin(), store_all_transactions=True)

        return {
            "database": database,
            "settings": settings,
            "max_peers": -1
        }


async def start_crawler(tribler_config):

    # We use our own community loader
    loader = IPv8CommunityLoader()
    loader.set_launcher(BandwidthCommunityCrawlerLauncher())
    session = Session(tribler_config, community_loader=loader)

    await session.start()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=('Start a crawler in the bandwidth accounting community'))
    parser.add_argument('--statedir', '-s', default='bw_crawler', type=str, help='Use an alternate statedir')
    parser.add_argument('--restapi', '-p', default=52194, type=str, help='Use an alternate port for the REST API',
                        action=PortAction, metavar='{0..65535}')
    args = parser.parse_args(sys.argv[1:])

    state_dir = Path(args.statedir).absolute()
    config = TriblerConfig.load(file=state_dir / 'triblerd.conf', state_dir=state_dir)

    config.tunnel_community.enabled = False
    config.libtorrent.enabled = False
    config.bootstrap.enabled = False
    config.chant.enabled = False
    config.torrent_checking.enabled = False
    config.api.http_enabled = True
    config.api.http_port = args.restapi

    loop = get_event_loop()
    coro = start_crawler(config)
    ensure_future(coro)
    loop.run_forever()
