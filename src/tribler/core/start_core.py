from __future__ import annotations

import logging.config
from asyncio import run
from typing import TYPE_CHECKING

from tribler.core.session import Session
from tribler.tribler_config import TriblerConfigManager

if TYPE_CHECKING:
    from pathlib import Path

logger = logging.getLogger(__name__)


async def run_session(config: TriblerConfigManager) -> None:
    """
    Start the Session and wait for it to shut itself down.
    """
    session = Session(config)
    await session.start()
    await session.shutdown_event.wait()
    await session.shutdown()


def run_core(api_port: int, api_key: str | None, state_dir: Path) -> None:
    """
    This method will start a new Tribler session.
    Note that there is no direct communication between the GUI process and the core: all communication is performed
    through the HTTP API.

    Returns an exit code value, which is non-zero if the Tribler session finished with an error.
    """
    logger.info("Start tribler core. API port: %d. API key: %s. State dir: %s.", api_port, api_key, state_dir)

    config = TriblerConfigManager(state_dir / "configuration.json")
    config.set("state_dir", str(state_dir))

    if config.get("api/refresh_port_on_start"):
        config.set("api/http_port", 0)
        config.set("api/https_port", 0)

    if api_key != config.get("api/key"):
        config.set("api/key", api_key)
        config.write()

    run(run_session(config))
