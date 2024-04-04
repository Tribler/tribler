from __future__ import annotations

import argparse
import asyncio
import typing
from pathlib import Path
import logging.config
import os
import sys

# https://github.com/pyinstaller/pyinstaller/issues/1113
import encodings.idna  # pylint: disable=unused-import

logger = logging.getLogger(__name__)


class Arguments(typing.TypedDict):
    torrent: str
    core: bool
    log_level: str


def parse_args() -> Arguments:
    parser = argparse.ArgumentParser(prog='Tribler [Experimental]', description='Run Tribler BitTorrent client')
    parser.add_argument('torrent', help='torrent file to download', default='', nargs='?')
    parser.add_argument('--core', action="store_true", help="run core process")
    parser.add_argument('--log-level', default="INFO", action="store_true", help="set the log level",
                        dest="log_level")
    return vars(parser.parse_args())


def get_root_state_directory(requested_path: os.PathLike | None) -> Path:
    """
    Get the default application state directory.
    """
    root_state_dir = Path(requested_path) if os.path.isabs(requested_path) else Path(os.getcwd(), requested_path)
    root_state_dir.mkdir(parents=True, exist_ok=True)
    return root_state_dir


def main():
    asyncio.set_event_loop(asyncio.SelectorEventLoop())

    parsed_args = parse_args()
    logging.basicConfig(level=getattr(logging, parsed_args["log_level"]), stream=sys.stdout)
    logger.info(f'Run Tribler: {parsed_args}')

    root_state_dir = get_root_state_directory(os.environ.get('TSTATEDIR', 'state_directory'))
    logger.info(f'Root state dir: {root_state_dir}')

    api_port, api_key = int(os.environ.get('CORE_API_PORT', '-1')), os.environ.get('CORE_API_KEY')

    # Check whether we need to start the core or the user interface
    if parsed_args["core"]:
        from tribler.core.start_core import run_core
        run_core(api_port, api_key, root_state_dir)
    else:
        # GUI
        from tribler.gui.start_gui import run_gui
        run_gui(api_port, api_key, root_state_dir)


if __name__ == "__main__":
    main()
