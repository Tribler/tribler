"""
This executable script starts a Tribler instance and joins the BandwidthAccountingCommunity.
"""
import argparse
import sys
from asyncio import ensure_future, get_event_loop
from pathlib import Path

from ipv8.loader import IPv8CommunityLoader

from tribler_core.config.tribler_config import TriblerConfig
from tribler_core.modules.bandwidth_accounting.database import BandwidthDatabase
from tribler_core.modules.bandwidth_accounting.settings import BandwidthAccountingSettings
from tribler_core.modules.ipv8_module_catalog import BandwidthCommunityLauncher
from tribler_core.session import Session


class PortAction(argparse.Action):
    def __call__(self, _, namespace, values, option_string=None):
        if not 0 < values < 2**16:
            raise argparse.ArgumentError(self, "Invalid port number")
        setattr(namespace, self.dest, values)


class BandwidthCommunityCrawlerLauncher(BandwidthCommunityLauncher):

    def get_kwargs(self, session):
        settings = BandwidthAccountingSettings()
        settings.outgoing_query_interval = 5
        database = BandwidthDatabase(session.config.get_state_dir() / "sqlite" / "bandwidth.db",
                                     session.trustchain_keypair.pub().key_to_bin(), store_all_transactions=True)

        return {
            "database": database,
            "settings": settings,
            "max_peers": -1
        }


async def start_crawler(tribler_config):
    session = Session(tribler_config)

    # We use our own community loader
    loader = IPv8CommunityLoader()
    session.ipv8_community_loader = loader
    loader.set_launcher(BandwidthCommunityCrawlerLauncher())

    await session.start()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=('Start a crawler in the bandwidth accounting community'))
    parser.add_argument('--statedir', '-s', default='bw_crawler', type=str, help='Use an alternate statedir')
    parser.add_argument('--restapi', '-p', default=52194, type=str, help='Use an alternate port for the REST API',
                        action=PortAction, metavar='{0..65535}')
    args = parser.parse_args(sys.argv[1:])

    config = TriblerConfig(args.statedir, config_file=Path(args.statedir) / 'triblerd.conf')
    config.set_state_dir(Path(args.statedir).absolute())
    config.set_tunnel_community_enabled(False)
    config.set_libtorrent_enabled(False)
    config.set_bootstrap_enabled(False)
    config.set_chant_enabled(False)
    config.set_torrent_checking_enabled(False)
    config.set_api_http_enabled(True)
    config.set_api_http_port(args.restapi)

    loop = get_event_loop()
    coro = start_crawler(config)
    ensure_future(coro)
    loop.run_forever()
