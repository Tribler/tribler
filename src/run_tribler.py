from __future__ import annotations

import argparse
import asyncio
import encodings.idna  # noqa: F401 (https://github.com/pyinstaller/pyinstaller/issues/1113)
import logging.config
import os
import sys
import threading
import typing
import webbrowser
from pathlib import Path

import pystray
from PIL import Image
from tribler.core.session import Session
from tribler.tribler_config import TriblerConfigManager

logger = logging.getLogger(__name__)


class Arguments(typing.TypedDict):
    """
    The possible command-line arguments to the core process.
    """

    torrent: str
    log_level: str


def parse_args() -> Arguments:
    """
    Parse the command-line arguments.
    """
    parser = argparse.ArgumentParser(prog='Tribler [Experimental]', description='Run Tribler BitTorrent client')
    parser.add_argument('torrent', help='torrent file to download', default='', nargs='?')
    parser.add_argument('--log-level', default="INFO", action="store_true", help="set the log level",
                        dest="log_level")
    return vars(parser.parse_args())


def get_root_state_directory(requested_path: os.PathLike | None) -> Path:
    """
    Get the default application state directory.
    """
    root_state_dir = (Path(requested_path) if os.path.isabs(requested_path)
                      else (Path(os.environ.get("APPDATA", "~")) / ".TriblerExperimental").expanduser().absolute())
    root_state_dir.mkdir(parents=True, exist_ok=True)
    return root_state_dir


async def main() -> None:
    """
    The main script entry point.
    """
    parsed_args = parse_args()
    logging.basicConfig(level=parsed_args["log_level"], stream=sys.stdout)
    logger.info("Run Tribler: %s", parsed_args)

    root_state_dir = get_root_state_directory(os.environ.get('TSTATEDIR', 'state_directory'))
    logger.info("Root state dir: %s", root_state_dir)

    api_port, api_key = int(os.environ.get('CORE_API_PORT', '0')), os.environ.get('CORE_API_KEY')

    config = TriblerConfigManager(root_state_dir / "configuration.json")
    config.set("state_dir", str(root_state_dir))

    if config.get("api/refresh_port_on_start"):
        config.set("api/http_port", 0)
        config.set("api/https_port", 0)

    if api_key is None and config.get("api/key") is None:
        api_key = os.urandom(16).hex()

    if api_key is not None and api_key != config.get("api/key"):
        config.set("api/key", api_key)
        config.write()

    if api_port is not None and api_port != config.get("api/http_port"):
        config.set("api/http_port", api_port)
        config.write()

    logger.info("Start tribler core. API port: %d. API key: %s.", api_port, config.get("api/key"))

    session = Session(config)
    await session.start()

    image_path = Path(__file__).absolute() / "../tribler/ui/public/tribler.png"
    image = Image.open(image_path.resolve())
    url = f"http://localhost:{session.rest_manager.get_api_port()}/ui/#/downloads/all?key={config.get('api/key')}"
    menu = (pystray.MenuItem('Open', lambda: webbrowser.open_new_tab(url)),
            pystray.MenuItem('Quit', lambda: session.shutdown_event.set()))
    icon = pystray.Icon("Tribler", icon=image, title="Tribler", menu=menu)
    threading.Thread(target=icon.run).start()

    await session.shutdown_event.wait()
    await session.shutdown()
    icon.stop()
    logger.info("Tribler shutdown completed")


if __name__ == "__main__":
    asyncio.set_event_loop(asyncio.SelectorEventLoop())
    asyncio.run(main())
