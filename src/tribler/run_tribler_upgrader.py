import logging
import signal
import sys

from tribler.core.components.key.key_component import KeyComponent
from tribler.core.config.tribler_config import TriblerConfig
from tribler.core.logger.logger import load_logger_config
from tribler.core.start_core import CONFIG_FILE_NAME
from tribler.core.upgrade.upgrade import TriblerUpgrader
from tribler.core.upgrade.version_manager import VersionHistory
from tribler.core.utilities.path_util import Path

logger = logging.getLogger(__name__)


def upgrade_state_dir(root_state_dir: Path,
                      update_status_callback=None,
                      interrupt_upgrade_event=None):
    logger.info('Upgrade state dir')
    # Before any upgrade, prepare a separate state directory for the update version so it does not
    # affect the older version state directory. This allows for safe rollback.
    version_history = VersionHistory(root_state_dir)
    version_history.fork_state_directory_if_necessary()
    version_history.save_if_necessary()
    state_dir = version_history.code_version.directory
    if not state_dir.exists():
        logger.info('State dir does not exist. Exit upgrade procedure.')
        return

    config = TriblerConfig.load(state_dir=state_dir, reset_config_on_error=True)
    channels_dir = config.chant.get_path_as_absolute('channels_dir', config.state_dir)

    primary_private_key_path = config.state_dir / KeyComponent.get_private_key_filename(config)
    primary_public_key_path = config.state_dir / config.trustchain.ec_keypair_pubfilename
    primary_key = KeyComponent.load_or_create(primary_private_key_path, primary_public_key_path)
    secondary_key = KeyComponent.load_or_create(config.state_dir / config.trustchain.secondary_key_filename)

    upgrader = TriblerUpgrader(state_dir, channels_dir, primary_key, secondary_key,
                               update_status_callback=update_status_callback,
                               interrupt_upgrade_event=interrupt_upgrade_event)
    upgrader.run()


if __name__ == "__main__":
    logger.info('Run')
    _upgrade_interrupted_event = []


    def interrupt_upgrade(*_):
        logger.info('Interrupt upgrade')
        _upgrade_interrupted_event.append(True)


    def upgrade_interrupted():
        return bool(_upgrade_interrupted_event)


    signal.signal(signal.SIGINT, interrupt_upgrade)
    signal.signal(signal.SIGTERM, interrupt_upgrade)
    _root_state_dir = Path(sys.argv[1])

    load_logger_config('upgrader', _root_state_dir)
    upgrade_state_dir(_root_state_dir, interrupt_upgrade_event=upgrade_interrupted)
