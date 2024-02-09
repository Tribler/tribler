"""
This script enables you to start a tunnel helper headless.
"""
import argparse
import logging
import os
import re
import sys
import time
from asyncio import get_running_loop, run
from ipaddress import AddressValueError, IPv4Address

from ipv8.messaging.anonymization.tunnel import Circuit
from ipv8.taskmanager import TaskManager
from ipv8.util import run_forever

from tribler.core import notifications
from tribler.core.components.ipv8.ipv8_component import Ipv8Component
from tribler.core.components.key.key_component import KeyComponent
from tribler.core.components.restapi.restapi_component import RESTComponent
from tribler.core.components.session import Session
from tribler.core.components.tunnel.tunnel_component import TunnelsComponent
from tribler.core.config.tribler_config import TriblerConfig
from tribler.core.utilities.osutils import get_root_state_directory
from tribler.core.utilities.path_util import Path
from tribler.core.utilities.utilities import make_async_loop_fragile

logger = logging.getLogger(__name__)


def components_gen():
    yield KeyComponent()
    yield RESTComponent()
    yield Ipv8Component()
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

    statedir = Path(os.path.join(get_root_state_directory(create=True), "tunnel-%d") % ipv8_port)
    config = TriblerConfig.load(state_dir=statedir)
    config.torrent_checking.enabled = False
    config.ipv8.enabled = True
    config.libtorrent.enabled = False
    config.ipv8.port = ipv8_port
    config.ipv8.address = options.ipv8_address
    config.dht.enabled = True
    config.tunnel_community.exitnode_enabled = bool(options.exit)
    config.content_discovery_community.enabled = False
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
        self.ipv8 = None

    def on_circuit_reject(self, reject_time, balance):
        with open(os.path.join(self.session.config.state_dir, "circuit_rejects.log"), 'a') as out_file:
            time_millis = int(round(reject_time * 1000))
            out_file.write("%d,%d\n" % (time_millis, balance))

    def tribler_started(self):
        component = self.session.get_instance(TunnelsComponent)
        tunnel_community = component.community
        self.register_task("bootstrap", tunnel_community.bootstrap, interval=30)

        # Remove all logging handlers
        root_logger = logging.getLogger()
        handlers = root_logger.handlers
        for handler in handlers:
            root_logger.removeHandler(handler)
        logging.getLogger().setLevel(logging.ERROR)

        self.ipv8 = self.session.get_instance(Ipv8Component).ipv8
        new_strategies = []
        with self.ipv8.overlay_lock:
            for strategy, target_peers in self.ipv8.strategies:
                if strategy.overlay == tunnel_community:
                    new_strategies.append((strategy, -1))
                else:
                    new_strategies.append((strategy, target_peers))
            self.ipv8.strategies = new_strategies

    def circuit_removed(self, circuit: Circuit, additional_info: str):
        self.ipv8.network.remove_by_address(circuit.peer.address)
        if self.log_circuits:
            with open(os.path.join(self.session.config.state_dir, "circuits.log"), 'a') as out_file:
                duration = time.time() - circuit.creation_time
                out_file.write("%d,%f,%d,%d,%s\n" % (circuit.circuit_id, duration, circuit.bytes_up, circuit.bytes_down,
                                                     additional_info))

    async def start(self, options):
        config = make_config(options)
        components = list(components_gen())
        session = self.session = Session(config, components)

        self.log_circuits = options.log_circuits
        session.notifier.add_observer(notifications.circuit_removed, self.circuit_removed)
        await session.start_components()
        if options.log_rejects:
            component = self.session.get_instance(TunnelsComponent)
            tunnels_community = component.community
            # We set this after Tribler has started since the tunnel_community won't be available otherwise
            tunnels_community.reject_callback = self.on_circuit_reject

        self.tribler_started()

    async def stop(self):
        if not self._stopping:
            self._stopping = True
            await self.shutdown_task_manager()
            await self.session.shutdown()


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


async def main():
    parser = argparse.ArgumentParser(add_help=False,
                                     description='Tunnel helper script, starts a (hidden) tunnel as a service')
    parser.add_argument('--help', '-h', action='help', default=argparse.SUPPRESS,
                        help='Show this help message and exit')
    parser.add_argument('--ipv8_port', '-d', default=-1, type=int, help='IPv8 port', action=PortAction,
                        metavar='{0..65535}')
    parser.add_argument('--ipv8_address', '-i', default='0.0.0.0', type=str, help='IPv8 listening address',
                        action=IPAction)
    parser.add_argument('--ipv8_bootstrap_override', '-b', default=None, type=str,
                        help='Force the usage of specific IPv8 bootstrap server (ip:port)', action=IPPortAction)
    parser.add_argument('--restapi', '-p', default=20100, type=int,
                        help='Use an alternate port for the REST API', action=PortAction, metavar='{0..65535}')
    parser.add_argument('--cert-file', '-e', help='Path to combined certificate/key file. If not given HTTP is used.')
    parser.add_argument('--api-key', '-k', help='API key to use. If not given API key protection is disabled.')
    parser.add_argument('--exit', '-x', action='store_const', default=False, const=True,
                        help='Allow being an exit-node')
    parser.add_argument('--testnet', '-t', action='store_const', default=False, const=True, help='Join the testnet')
    parser.add_argument('--no-rest-api', '-a', action='store_const', default=False, const=True,
                        help='Disable the REST api')
    parser.add_argument('--log-rejects', action='store_const', default=False, const=True, help='Log rejects')
    parser.add_argument('--log-circuits', action='store_const', default=False, const=True,
                        help='Log information about circuits')
    parser.add_argument('--fragile', '-f', help='Fail at the first error', action='store_true')

    args = parser.parse_args(sys.argv[1:])
    if args.fragile:
        make_async_loop_fragile(get_running_loop())

    service = TunnelHelperService()
    await service.start(args)
    await run_forever()
    await service.stop()


if __name__ == "__main__":
    run(main())
