import logging
import sys
from pathlib import Path
from typing import Optional

from tribler.gui.tribler_app import TriblerApplication
from tribler.gui.tribler_window import TriblerWindow

logger = logging.getLogger(__name__)


def run_gui(api_port: Optional[int], api_key: Optional[str], root_state_dir: Path):
    app = TriblerApplication()
    logger.info('Start Tribler Window')
    window = TriblerWindow(app.manager, root_state_dir, api_port, api_key=api_key)
    window.setWindowTitle("Tribler")
    app.tribler_window = window
    app.parse_sys_args(sys.argv)
    app.exec_()
