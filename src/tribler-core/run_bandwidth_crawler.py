"""
This executable script starts a Tribler instance and joins the BandwidthAccountingCommunity.

This bandwidth crawler optionally support a payout file. This is used to payout the old balances of users during
the migration from Tribler 7.5 to 7.6. We will keep track of who we did payout already in a separate file to avoid
payout out twice.
"""
import argparse
import os
import sys
from asyncio import ensure_future, get_event_loop
from binascii import hexlify, unhexlify
from pathlib import Path

from ipv8.loader import IPv8CommunityLoader, overlay

from tribler_core.config.tribler_config import TriblerConfig
from tribler_core.modules.bandwidth_accounting.community import BandwidthAccountingCommunity
from tribler_core.modules.bandwidth_accounting.database import BandwidthDatabase
from tribler_core.modules.bandwidth_accounting.settings import BandwidthAccountingSettings
from tribler_core.modules.ipv8_module_catalog import BandwidthCommunityLauncher
from tribler_core.session import Session


class PortAction(argparse.Action):
    def __call__(self, _, namespace, values, option_string=None):
        if not 0 < values < 2**16:
            raise argparse.ArgumentError(self, "Invalid port number")
        setattr(namespace, self.dest, values)


class BandwidthAccountingCrawlerCommunity(BandwidthAccountingCommunity):

    def __init__(self, *args, **kwargs) -> None:
        self.payouts_info = kwargs.pop('payouts_info', {})
        self.tribler_session = kwargs.pop('tribler_session', None)
        super().__init__(*args, **kwargs)
        self.performed_payouts = set()  # Keep track of the peers to which we already did a payout

        if self.payouts_info:
            if os.path.exists(self.tribler_session.config.get_state_dir() / "performed_payouts.txt"):
                with open(self.tribler_session.config.get_state_dir() / "performed_payouts.txt") as \
                        performed_payouts_file:
                    for line in performed_payouts_file.readlines():
                        pub_key = unhexlify(line.strip())
                        self.performed_payouts.add(pub_key)
            self.logger.info("Loaded %d performed payouts!", len(self.performed_payouts))
            self.register_task("compensate_peers", self.perform_compensation_payouts, interval=60)

    def perform_compensation_payouts(self):
        """
        Perform compensation payouts, based on the provided payout information.
        """
        self.logger.info("Checking if we have to compensate users!")
        for peer in self.network.verified_peers:
            if peer.public_key.key_to_bin() in self.payouts_info:
                if peer.public_key.key_to_bin() not in self.performed_payouts:
                    to_payout = self.payouts_info[peer.public_key.key_to_bin()]
                    self.logger.info("Will perform compensation payout of %d to %s!",
                                     to_payout, hexlify(peer.public_key.key_to_bin()))

                    ensure_future(self.do_payout(peer, to_payout))

                    # Record this payout
                    hex_pk = hexlify(peer.public_key.key_to_bin()).decode()
                    self.performed_payouts.add(peer.public_key.key_to_bin())
                    with open(self.tribler_session.config.get_state_dir() / "performed_payouts.txt",
                              "a") as performed_payouts_file:
                        performed_payouts_file.write("%s\n" % hex_pk)


def bandwidth_accounting_community():
    return BandwidthAccountingCrawlerCommunity


@overlay(bandwidth_accounting_community)
class BandwidthCommunityCrawlerLauncher(BandwidthCommunityLauncher):

    def __init__(self, payouts_info):
        super().__init__()
        self.payouts_info = payouts_info

    def get_kwargs(self, session):
        settings = BandwidthAccountingSettings()
        settings.outgoing_query_interval = 5
        database = BandwidthDatabase(session.config.get_state_dir() / "sqlite" / "bandwidth.db",
                                     session.trustchain_keypair.pub().key_to_bin(), store_all_transactions=True)

        return {
            "database": database,
            "settings": settings,
            "max_peers": -1,
            "payouts_info": self.payouts_info,
            "tribler_session": session,
        }


async def start_crawler(tribler_config, payouts_info):
    session = Session(tribler_config)

    # We use our own community loader
    loader = IPv8CommunityLoader()
    session.ipv8_community_loader = loader
    loader.set_launcher(BandwidthCommunityCrawlerLauncher(payouts_info))

    await session.start()

    print("Tribler started!")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=('Start a crawler in the bandwidth accounting community'))
    parser.add_argument('--statedir', '-s', default='bw_crawler', type=str, help='Use an alternate statedir')
    parser.add_argument('--payoutsfile', '-f', default=None, type=str, help='A file containing payout information')
    parser.add_argument('--restapi', '-p', default=8085, type=str, help='Use an alternate port for the REST API',
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

    payouts_info = {}
    if args.payoutsfile:
        if not os.path.exists(args.payoutsfile):
            print("Payout file does not exist!")
        else:
            # We assume that the payouts CSV file contains lines with a hex-encoded public key and the old balance in
            # bytes.
            print("Will parse payout file %s..." % args.payoutsfile)
            with open(args.payoutsfile, "r") as payouts_file:
                parsed_header = False
                for line in payouts_file.readlines():
                    if not parsed_header:
                        parsed_header = True
                        continue
                    parts = line.strip().split(",")
                    pub_key = unhexlify(parts[0])
                    balance = int(parts[1]) - int(parts[2])
                    if balance > 0:  # We only payout to users with a positive balance
                        payouts_info[pub_key] = balance

            print("Scheduling payouts for %d user(s)!" % len(payouts_info))

    loop = get_event_loop()
    coro = start_crawler(config, payouts_info)
    ensure_future(coro)
    loop.run_forever()
