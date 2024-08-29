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
from aiohttp import ClientSession
from PIL import Image

import tribler
from tribler.core.session import Session
from tribler.tribler_config import VERSION_SUBDIR, TriblerConfigManager

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
                      else (Path(os.environ.get("APPDATA", "~")) / ".Tribler").expanduser().absolute())
    root_state_dir.mkdir(parents=True, exist_ok=True)
    return root_state_dir


async def start_download(config: TriblerConfigManager, server_url: str, torrent_uri: str) -> None:
    """
    Start a download by calling the REST API.
    """
    async with ClientSession() as client, client.put(server_url + "/api/downloads",
                                                     headers={"X-Api-Key": config.get("api/key")},
                                                     json={"uri": torrent_uri}) as response:
        if response.status == 200:
            logger.info("Successfully started torrent %s", torrent_uri)
        else:
            logger.warning("Failed to start torrent %s: %s", torrent_uri, await response.text())


async def main() -> None:
    """
    The main script entry point.
    """
    parsed_args = parse_args()
    logging.basicConfig(level=parsed_args["log_level"], stream=sys.stdout)
    logger.info("Run Tribler: %s", parsed_args)

    root_state_dir = get_root_state_directory(os.environ.get('TSTATEDIR', 'state_directory'))
    (root_state_dir / VERSION_SUBDIR).mkdir(exist_ok=True, parents=True)
    logger.info("Root state dir: %s", root_state_dir)
    config = TriblerConfigManager(root_state_dir / VERSION_SUBDIR / "configuration.json")
    config.set("state_dir", str(root_state_dir))

    if "CORE_API_PORT" in os.environ:
        config.set("api/http_port", int(os.environ.get("CORE_API_PORT")))
        config.write()

    if "CORE_API_KEY" in os.environ:
        config.set("api/key", os.environ.get("CORE_API_KEY"))
        config.write()

    if config.get("api/key") is None:
        config.set("api/key", os.urandom(16).hex())
        config.write()

    logger.info("Creating session. API port: %d. API key: %s.", config.get("api/http_port"), config.get("api/key"))
    session = Session(config)

    torrent_uri = parsed_args.get('torrent')
    if torrent_uri and os.path.exists(torrent_uri):
        if torrent_uri.endswith(".torrent"):
            torrent_uri = Path(torrent_uri).as_uri()
        if torrent_uri.endswith(".magnet"):
            torrent_uri = Path(torrent_uri).read_text()
    server_url = await session.find_api_server()

    if server_url:
        logger.info("Core already running at %s", server_url)
        if torrent_uri:
            logger.info("Starting torrent using existing core")
            await start_download(config, server_url, torrent_uri)
        webbrowser.open_new_tab(server_url + f"?key={config.get('api/key')}")
        logger.info("Shutting down")
        return

    await session.start()

    server_url = await session.find_api_server()
    if server_url and torrent_uri:
        await start_download(config, server_url, torrent_uri)

    image_path = tribler.get_webui_root() / "public" / "tribler.png"
    image = Image.open(image_path.resolve())
    api_port = session.rest_manager.get_api_port()
    url = f"http://{config.get('api/http_host')}:{api_port}/ui/#/downloads/all?key={config.get('api/key')}"
    menu = (pystray.MenuItem('Open', lambda: webbrowser.open_new_tab(url)),
            pystray.MenuItem('Quit', lambda: session.shutdown_event.set()))
    icon = pystray.Icon("Tribler", icon=image, title="Tribler", menu=menu)
    webbrowser.open_new_tab(url)
    threading.Thread(target=icon.run).start()

    await session.shutdown_event.wait()
    await session.shutdown()
    icon.stop()
    logger.info("Tribler shutdown completed")


if __name__ == "__main__":
    asyncio.set_event_loop(asyncio.SelectorEventLoop())
    asyncio.run(main())
