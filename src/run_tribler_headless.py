"""
This script enables you to start Tribler headless.
"""
import argparse
import logging
import os
import re
import signal
import sys
import time
from asyncio import ensure_future, get_event_loop, sleep
from datetime import date
from socket import inet_aton
from typing import Optional

from filelock import FileLock

from tribler.core.components.session import Session
from tribler.core.config.tribler_config import TriblerConfig
from tribler.core.start_core import components_gen
from tribler.core.upgrade.version_manager import VersionHistory
from tribler.core.utilities.exit_codes.tribler_exit_codes import EXITCODE_ANOTHER_CORE_PROCESS_IS_RUNNING
from tribler.core.utilities.osutils import get_appstate_dir, get_root_state_directory
from tribler.core.utilities.path_util import Path
from tribler.core.utilities.process_locking import CORE_LOCK_FILENAME, try_acquire_file_lock
from tribler.core.utilities.process_manager import ProcessKind, ProcessManager
from tribler.core.utilities.process_manager.manager import setup_process_manager


class IPPortAction(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
        parsed = re.match(r"^([\d\.]+)\:(\d+)$", values)
        if not parsed:
            raise argparse.ArgumentError(self, "Invalid address:port")

        ip, port = parsed.group(1), int(parsed.group(2))
        try:
            inet_aton(ip)
        except:
            raise argparse.ArgumentError(self, "Invalid server address")

        if not (0 < port < 65535):
            raise argparse.ArgumentError(self, "Invalid server port")
        setattr(namespace, self.dest, values)


class TriblerService:

    def __init__(self):
        """
        Initialize the variables of the TriblerServiceMaker and the logger.
        """
        self.session = None
        self._stopping = False
        self.process_lock: Optional[FileLock] = None
        self.process_manager: Optional[ProcessManager] = None

    def log_incoming_remote_search(self, sock_addr, keywords):
        d = date.today()
        with open(os.path.join(self.session.config.state_dir, f'incoming-searches-{d.isoformat()}'),
                  'a') as log_file:
            log_file.write(f"{time.time()} {sock_addr[0]} {sock_addr[1]} {';'.join(keywords)}")

    async def start_tribler(self, options):
        """
        Main method to startup Tribler.
        """

        async def signal_handler(sig):
            print(f"Received shut down signal {sig}")
            if not self._stopping:
                self._stopping = True
                await self.session.shutdown()
                print("Tribler shut down")
                get_event_loop().stop()
                self.process_manager.current_process.finish()
                self.process_lock.release()

        signal.signal(signal.SIGINT, lambda sig, _: ensure_future(signal_handler(sig)))
        signal.signal(signal.SIGTERM, lambda sig, _: ensure_future(signal_handler(sig)))

        if options.statedir:
            os.environ['TSTATEDIR'] = options.statedir

        root_state_dir = get_root_state_directory(create=True)
        version_history = VersionHistory(root_state_dir)
        statedir = version_history.code_version.directory
        config = TriblerConfig.load(state_dir=statedir)

        self.process_lock = try_acquire_file_lock(root_state_dir / CORE_LOCK_FILENAME)
        current_process_owns_lock = bool(self.process_lock)

        self.process_manager = setup_process_manager(root_state_dir, ProcessKind.Core, current_process_owns_lock)

        if not current_process_owns_lock:
            msg = 'Another Core process is already running'
            print(msg)
            self.process_manager.sys_exit(EXITCODE_ANOTHER_CORE_PROCESS_IS_RUNNING, msg)

        print("Starting Tribler")

        http_port = options.restapi_http_port or int(os.environ.get('CORE_API_PORT', "0"))

        if 'CORE_API_PORT' in os.environ and (http_port := int(os.environ.get('CORE_API_PORT'))) > 0:
            config.api.http_port = http_port
        elif options.restapi_http_port > 0:
            config.api.http_port = options.restapi_http_port

        if options.restapi_http_host:
            config.api.http_host = options.restapi_http_host

        if options.restapi_https_port > 0:
            config.api.https_port = options.restapi_https_port

        if options.restapi_https_host:
            config.api.https_host = options.restapi_https_host

        if config.api.http_port > 0:
            config.api.http_enabled = True

        if config.api.https_port > 0:
            config.api.https_enabled = True

        if api_key := os.environ.get('CORE_API_KEY'):
            config.api.key = api_key

        if options.ipv8 > 0:
            config.ipv8.port = options.ipv8
        elif options.ipv8 == 0:
            config.ipv8.enabled = False

        if options.libtorrent != -1 and options.libtorrent > 0:
            config.libtorrent.port = options.libtorrent

        if options.download_dir:
            config.download_defaults.saveas = options.download_dir

        if options.ipv8_bootstrap_override is not None:
            config.ipv8.bootstrap_override = options.ipv8_bootstrap_override

        if options.testnet:
            config.tunnel_community.testnet = True
            config.chant.testnet = True

        self.session = Session(config, components=list(components_gen(config)))
        try:
            await self.session.start_components()
        except Exception as e:
            print(str(e))
            get_event_loop().stop()
        else:
            print("Tribler started")


def setup_logger(verbosity):
    logging_level = logging.DEBUG if verbosity else logging.INFO
    logging.basicConfig(level=logging_level)


def main(argv):
    parser = argparse.ArgumentParser(add_help=False, description=('Tribler script, starts Tribler as a service'))
    parser.add_argument('--help', '-h', action='help', default=argparse.SUPPRESS,
                        help='Show this help message and exit')
    parser.add_argument('--statedir', '-s', default=None, help='Use an alternate statedir')
    parser.add_argument('--download_dir', default=None, help='Use an alternative download directory')
    parser.add_argument('--restapi_http_port', '--restapi', '-p', default=-1, type=int,
                        help='Use an alternate port for http REST API')
    parser.add_argument('--restapi_http_host', default=None, type=str,
                        help='Use an alternate listen address for http REST API')
    parser.add_argument('--restapi_https_port', default=-1, type=int,
                        help='Use an alternate port for https REST API')
    parser.add_argument('--restapi_https_host', default=None, type=str,
                        help='Use an alternate listen address for https REST API')
    parser.add_argument('--ipv8', '-i', default=-1, type=int, help='Use an alternate port for the IPv8')
    parser.add_argument('--libtorrent', '-l', default=-1, type=int, help='Use an alternate port for libtorrent')
    parser.add_argument('--ipv8_bootstrap_override', '-b', default=None, type=str,
                        help='Force the usage of specific IPv8 bootstrap server (ip:port)', action=IPPortAction)

    parser.add_argument('--testnet', '-t', action='store_const', default=False, const=True, help='Join the testnet')
    parser.add_argument('-v', '--verbosity', help='increase output verbosity', action='store_true')

    args = parser.parse_args(sys.argv[1:])
    setup_logger(args.verbosity)
    service = TriblerService()

    loop = get_event_loop()
    coro = service.start_tribler(args)
    ensure_future(coro)

    if sys.platform == 'win32' and sys.version_info < (3, 8):
        # Unfortunately, this is needed on Windows for Ctrl+C to work consistently.
        # Should no longer be needed in Python 3.8.
        async def wakeup():
            while True:
                await sleep(1)

        ensure_future(wakeup())

    loop.run_forever()


if __name__ == "__main__":
    main(sys.argv[1:])
