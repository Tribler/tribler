"""
This script enables you to start a tunnel helper headless.
"""
import argparse
import logging
import os
import re
import signal
import sys
import time
from asyncio import ensure_future, get_event_loop
from ipaddress import AddressValueError, IPv4Address

from ipv8.taskmanager import TaskManager

from tribler_common.osutils import get_root_state_directory
from tribler_common.simpledefs import NTFY

from tribler_core.components.bandwidth_accounting.bandwidth_accounting_component import BandwidthAccountingComponent
from tribler_core.components.base import Session
from tribler_core.components.ipv8.ipv8_component import Ipv8Component
from tribler_core.components.key.key_component import KeyComponent
from tribler_core.components.resource_monitor.resource_monitor_component import ResourceMonitorComponent
from tribler_core.components.restapi.restapi_component import RESTComponent
from tribler_core.components.socks_servers.socks_servers_component import SocksServersComponent
from tribler_core.components.tunnel.tunnel_component import TunnelsComponent
from tribler_core.components.upgrade import UpgradeComponent
from tribler_core.config.tribler_config import TriblerConfig
from tribler_core.utilities.path_util import Path

logger = logging.getLogger(__name__)


def components_gen():
    yield KeyComponent()
    yield UpgradeComponent()
    yield RESTComponent()
    yield Ipv8Component()
    yield ResourceMonitorComponent()
    yield BandwidthAccountingComponent()
    yield SocksServersComponent()
    yield TunnelsComponent()


def make_config(options) -> TriblerConfig:
    # Determine ipv8 port
    ipv8_port = options.ipv8_port
    if ipv8_port == -1:
        if "HELPER_INDEX" in os.environ and "HELPER_BASE" in os.environ:
            base_port = int(os.environ["HELPER_BASE"])
            ipv8_port = base_port + int(os.environ["HELPER_INDEX"]) * 5
        else:
            raise ValueError('ipv8_port option is not set, and HELPER_BASE/HELPER_INDEX env vars are not defined')

    statedir = Path(os.path.join(get_root_state_directory(), "tunnel-%d") % ipv8_port)
    config = TriblerConfig.load(file=statedir / 'triblerd.conf', state_dir=statedir)
    config.tunnel_community.random_slots = options.random_slots
    config.tunnel_community.competing_slots = options.competing_slots
    config.torrent_checking.enabled = False
    config.ipv8.enabled = True
    config.libtorrent.enabled = False
    config.ipv8.port = ipv8_port
    config.ipv8.address = options.ipv8_address
    config.dht.enabled = True
    config.tunnel_community.exitnode_enabled = bool(options.exit)
    config.popularity_community.enabled = False
    config.tunnel_community.testnet = bool(options.testnet)
    config.chant.enabled = False
    config.bootstrap.enabled = False

    if not options.no_rest_api:
        https = bool(options.cert_file)
        config.api.https_enabled = https
        config.api.http_enabled = not https
        config.api.key = options.api_key

        api_port = options.restapi
        if "HELPER_INDEX" in os.environ and "HELPER_BASE" in os.environ:
            api_port = int(os.environ["HELPER_BASE"]) + 10000 + int(os.environ["HELPER_INDEX"])
        if https:
            config.api.https_port = api_port
            config.api.put_path_as_relative('https_certfile', options.cert_file, config.state_dir)
        else:
            config.api.http_port = api_port
    else:
        config.api.https_enabled = False
        config.api.http_enabled = False

    if options.ipv8_bootstrap_override is not None:
        config.ipv8.bootstrap_override = options.ipv8_bootstrap_override
    return config


class TunnelHelperService(TaskManager):

    def __init__(self):
        super().__init__()
        self._stopping = False
        self.log_circuits = False
        self.session = None
        self.community = None

    def on_circuit_reject(self, reject_time, balance):
        with open(os.path.join(self.session.config.state_dir, "circuit_rejects.log"), 'a') as out_file:
            time_millis = int(round(reject_time * 1000))
            out_file.write("%d,%d\n" % (time_millis, balance))

    def tribler_started(self):
        async def signal_handler(sig):
            print(f"Received shut down signal {sig}")  # noqa: T001
            await self.stop()

        signal.signal(signal.SIGINT, lambda sig, _: ensure_future(signal_handler(sig)))
        signal.signal(signal.SIGTERM, lambda sig, _: ensure_future(signal_handler(sig)))

        tunnel_community = TunnelsComponent.instance().community
        self.register_task("bootstrap", tunnel_community.bootstrap, interval=30)

        # Remove all logging handlers
        root_logger = logging.getLogger()
        handlers = root_logger.handlers
        for handler in handlers:
            root_logger.removeHandler(handler)
        logging.getLogger().setLevel(logging.ERROR)

        ipv8 = Ipv8Component.instance().ipv8
        new_strategies = []
        with ipv8.overlay_lock:
            for strategy, target_peers in ipv8.strategies:
                if strategy.overlay == tunnel_community:
                    new_strategies.append((strategy, -1))
                else:
                    new_strategies.append((strategy, target_peers))
            ipv8.strategies = new_strategies

    def circuit_removed(self, circuit, additional_info):
        ipv8 = Ipv8Component.instance().ipv8
        ipv8.network.remove_by_address(circuit.peer.address)
        if self.log_circuits:
            with open(os.path.join(self.session.config.state_dir, "circuits.log"), 'a') as out_file:
                duration = time.time() - circuit.creation_time
                out_file.write("%d,%f,%d,%d,%s\n" % (circuit.circuit_id, duration, circuit.bytes_up, circuit.bytes_down,
                                                     additional_info))

    async def start(self, options):
        config = make_config(options)
        components = list(components_gen())
        session = self.session = Session(config, components)
        session.set_as_default()

        self.log_circuits = options.log_circuits
        session.notifier.add_observer(NTFY.TUNNEL_REMOVE, self.circuit_removed)

        await session.start()

        with session:
            if options.log_rejects:
                tunnels_component = TunnelsComponent.instance()
                tunnels_community = tunnels_component.community
                # We set this after Tribler has started since the tunnel_community won't be available otherwise
                tunnels_community.reject_callback = self.on_circuit_reject

        self.tribler_started()

    async def stop(self):
        if not self._stopping:
            self._stopping = True
            self.session.shutdown_event.set()
            await self.shutdown_task_manager()
            await self.session.shutdown()
            get_event_loop().stop()


class PortAction(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
        if not 0 < values < 2 ** 16:
            raise argparse.ArgumentError(self, "Invalid port number")
        setattr(namespace, self.dest, values)


class IPAction(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
        try:
            IPv4Address(values)
        except AddressValueError as e:
            raise argparse.ArgumentError(self, "Invalid IPv4 address") from e
        setattr(namespace, self.dest, values)


class IPPortAction(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
        parsed = re.match(r"^([\d\.]+)\:(\d+)$", values)
        if not parsed:
            raise argparse.ArgumentError(self, "Invalid address:port")

        ip, port = parsed.group(1), int(parsed.group(2))
        try:
            IPv4Address(ip)
        except AddressValueError as e:
            raise argparse.ArgumentError(self, "Invalid server address") from e

        if not 0 < port < 65535:
            raise argparse.ArgumentError(self, "Invalid server port")
        setattr(namespace, self.dest, values)


def main():
    parser = argparse.ArgumentParser(add_help=False,
                                     description=('Tunnel helper script, starts a (hidden) tunnel as a service'))
    parser.add_argument('--help', '-h', action='help', default=argparse.SUPPRESS,
                        help='Show this help message and exit')
    parser.add_argument('--ipv8_port', '-d', default=-1, type=int, help='IPv8 port', action=PortAction,
                        metavar='{0..65535}')
    parser.add_argument('--ipv8_address', '-i', default='0.0.0.0', type=str, help='IPv8 listening address',
                        action=IPAction)
    parser.add_argument('--ipv8_bootstrap_override', '-b', default=None, type=str,
                        help='Force the usage of specific IPv8 bootstrap server (ip:port)', action=IPPortAction)
    parser.add_argument('--restapi', '-p', default=52194, type=int,
                        help='Use an alternate port for the REST API', action=PortAction, metavar='{0..65535}')
    parser.add_argument('--cert-file', '-e', help='Path to combined certificate/key file. If not given HTTP is used.')
    parser.add_argument('--api-key', '-k', help='API key to use. If not given API key protection is disabled.')
    parser.add_argument('--random_slots', '-r', default=10, type=int, help='Specifies the number of random slots')
    parser.add_argument('--competing_slots', '-c', default=20, type=int, help='Specifies the number of competing slots')
    parser.add_argument('--exit', '-x', action='store_const', default=False, const=True,
                        help='Allow being an exit-node')
    parser.add_argument('--testnet', '-t', action='store_const', default=False, const=True, help='Join the testnet')
    parser.add_argument('--no-rest-api', '-a', action='store_const', default=False, const=True,
                        help='Disable the REST api')
    parser.add_argument('--log-rejects', action='store_const', default=False, const=True, help='Log rejects')
    parser.add_argument('--log-circuits', action='store_const', default=False, const=True,
                        help='Log information about circuits')

    args = parser.parse_args(sys.argv[1:])
    service = TunnelHelperService()

    loop = get_event_loop()
    coro = service.start(args)
    ensure_future(coro)

    loop.run_forever()


if __name__ == "__main__":
    main()
