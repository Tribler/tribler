from __future__ import annotations

import sys
import traceback
from typing import TYPE_CHECKING, overload

if TYPE_CHECKING:
    from typing import Literal, NoReturn

    from pystray import Icon


@overload
def show_error(exc: Exception, shutdown: Literal[True] = True) -> NoReturn:
    ...


@overload
def show_error(exc: Exception, shutdown: Literal[False] = True) -> None:
    ...


def show_error(exc: Exception, shutdown: bool = True) -> NoReturn:
    """
    Create a native pop-up without any third party dependency.

    :param exc: the error to show to the user
    :param shutdown: whether to shut down after showing the error
    """
    title = f"A {exc.__class__.__name__} occurred"
    text = "\n\n".join([str(a) for a in exc.args])
    sep = "*" * 80

    print('\n'.join([sep, title, sep, traceback.format_exc(), sep]), file=sys.stderr)  # noqa: T201, FLY002
    try:
        if sys.platform == 'win32':
            import win32api

            win32api.MessageBox(0, text, title)
        elif sys.platform == 'linux':
            import subprocess

            subprocess.Popen(['xmessage', '-center', text])  # noqa: S603, S607
        elif sys.platform == 'darwin':
            import subprocess

            subprocess.Popen(['/usr/bin/osascript', '-e', text])  # noqa: S603
        else:
            print(f'cannot create native pop-up for system {sys.platform}')  # noqa: T201
    except Exception as exception:
        # Use base Exception, because code above can raise many
        # non-obvious types of exceptions:
        # (SubprocessError, ImportError, win32api.error, FileNotFoundError)
        print(f'Error while showing a message box: {exception}')  # noqa: T201

    if shutdown:
        sys.exit(1)


try:
    import argparse
    import asyncio
    import encodings.idna  # noqa: F401 (https://github.com/pyinstaller/pyinstaller/issues/1113)
    import logging.config
    import os
    import threading
    import typing
    import webbrowser
    from pathlib import Path

    from aiohttp import ClientSession
    from PIL import Image

    import tribler
    from tribler.core.session import Session
    from tribler.tribler_config import VERSION_SUBDIR, TriblerConfigManager

except Exception as e:
    show_error(e, True)

logger = logging.getLogger(__name__)


class Arguments(typing.TypedDict):
    """
    The possible command-line arguments to the core process.
    """

    torrent: str
    log_level: str
    server: bool


def parse_args() -> Arguments:
    """
    Parse the command-line arguments.
    """
    parser = argparse.ArgumentParser(prog='Tribler', description='Run Tribler BitTorrent client')
    parser.add_argument('torrent', help='Torrent file to download', default='', nargs='?')
    parser.add_argument('--log-level', default="INFO", action="store", nargs='?',
                        help="Set the log level. The default is 'INFO'",
                        choices=['CRITICAL', 'ERROR', 'WARNING', 'INFO', 'DEBUG', 'NOTSET'],
                        dest="log_level")
    parser.add_argument('-s', '--server', action='store_true', help="Run headless as a server without graphical pystray interface")
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


def init_config(parsed_args: Arguments) -> TriblerConfigManager:
    """
    Add environment variables to the configuration.
    """
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
    return config


def load_torrent_uri(parsed_args: Arguments) -> str | None:
    """
    Loads the torrent URI.
    """
    torrent_uri = parsed_args.get('torrent')
    if torrent_uri and os.path.exists(torrent_uri):
        if torrent_uri.endswith(".torrent"):
            torrent_uri = Path(torrent_uri).as_uri()
        if torrent_uri.endswith(".magnet"):
            torrent_uri = Path(torrent_uri).read_text()
    return torrent_uri


async def mac_event_loop() -> None:
    """
    Consume Mac events on the asyncio main thread.

    WARNING: ``sendEvent_`` can block on some events. In particular, while the tray menu is open.
    """
    from AppKit import NSApp, NSEventMaskAny
    from Foundation import NSDate, NSDefaultRunLoopMode

    while True:
        event = NSApp().nextEventMatchingMask_untilDate_inMode_dequeue_(NSEventMaskAny, NSDate.now(),
                                                                        NSDefaultRunLoopMode, True)
        if event is None:
            await asyncio.sleep(0.5)
        else:
            NSApp().sendEvent_(event)
            await asyncio.sleep(0.01)


def open_webbrowser_tab(url: str) -> None:
    """
    Open a webbrowser tab with the given URL.
    """
    if sys.platform == "darwin":
        os.system(f"open {url}")  # noqa: S605
    else:
        webbrowser.open_new_tab(url)


def spawn_tray_icon(session: Session, config: TriblerConfigManager) -> Icon:
    """
    Create the tray icon.
    """
    import pystray
    image_path = tribler.get_webui_root() / "public" / "tribler.png"
    image = Image.open(image_path.resolve())
    api_port = session.rest_manager.get_api_port()
    url = f"http://{config.get('api/http_host')}:{api_port}/ui/#/downloads/all?key={config.get('api/key')}"
    menu = (pystray.MenuItem('Open', lambda: open_webbrowser_tab(url)),
            pystray.MenuItem('Quit', lambda: session.shutdown_event.set()))
    icon = pystray.Icon("Tribler", icon=image, title="Tribler", menu=menu)
    open_webbrowser_tab(url)
    if sys.platform == "darwin":
        icon.run_detached(None)
        asyncio.ensure_future(mac_event_loop())  # noqa: RUF006
    else:
        threading.Thread(target=icon.run).start()
    return icon


async def main() -> None:
    """
    The main script entry point.
    """
    try:
        parsed_args = parse_args()
        config = init_config(parsed_args)

        logger.info("Creating session. API port: %d. API key: %s.", config.get("api/http_port"), config.get("api/key"))
        session = Session(config)

        torrent_uri = load_torrent_uri(parsed_args)
        server_url = await session.find_api_server()

        headless = parsed_args.get("server")
        if server_url:
            logger.info("Core already running at %s", server_url)
            if torrent_uri:
                logger.info("Starting torrent using existing core")
                await start_download(config, server_url, torrent_uri)
            if not headless:
                open_webbrowser_tab(server_url + f"?key={config.get('api/key')}")
            logger.info("Shutting down")
            return

        await session.start()
    except Exception as exc:
        show_error(exc, True)

    server_url = await session.find_api_server()
    if server_url and torrent_uri:
        await start_download(config, server_url, torrent_uri)
    icon = None if headless else spawn_tray_icon(session, config)

    await session.shutdown_event.wait()
    await session.shutdown()
    if icon:
        icon.stop()
    logger.info("Tribler shutdown completed")


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
