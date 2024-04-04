from __future__ import annotations

import logging.config
from asyncio import run
from pathlib import Path

from tribler.core.session import Session
from tribler.tribler_config import TriblerConfigManager

logger = logging.getLogger(__name__)
CONFIG_FILE_NAME = 'triblerd.conf'


async def run_session(config: TriblerConfigManager) -> None:
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
    logger.info(f'Start tribler core. API port: "{api_port}". API key: "{api_key}". State dir: "{state_dir}".')

    config = TriblerConfigManager(state_dir / "configuration.json")
    config.set("state_dir", str(state_dir))
    if api_key is None:
        config.set("api/key", api_key)
        config.write()

    run(run_session(config))
