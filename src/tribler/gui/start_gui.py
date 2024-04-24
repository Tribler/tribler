import logging
import os
import sys
from pathlib import Path
from typing import Optional

from tribler.gui.tribler_app import TriblerApplication
from tribler.gui.tribler_window import TriblerWindow

logger = logging.getLogger(__name__)


def run_gui(api_port: Optional[int], api_key: Optional[str], root_state_dir: Path):
    # Workaround for macOS Big Sur and later, see https://github.com/Tribler/tribler/issues/5728
    if sys.platform == "darwin":
        logger.info('Enabling a workaround for macOS Big Sur')
        os.environ["QT_MAC_WANTS_LAYER"] = "1"
    # Workaround for Ubuntu 21.04+, see https://github.com/Tribler/tribler/issues/6701
    elif sys.platform == "linux":
        logger.info('Enabling a workaround for Ubuntu 21.04+ wayland environment')
        os.environ["GDK_BACKEND"] = "x11"

    app = TriblerApplication()
    logger.info('Start Tribler Window')
    window = TriblerWindow(app.manager, root_state_dir, api_port, api_key=api_key)
    window.setWindowTitle("Tribler")
    app.tribler_window = window
    app.parse_sys_args(sys.argv)
    app.exec_()
