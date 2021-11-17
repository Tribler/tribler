import signal
import sys

from tribler_common.simpledefs import UpgradeInterruptedEvent
from tribler_common.version_manager import VersionHistory

from tribler_core.components.key.key_component import KeyComponent
from tribler_core.config.tribler_config import TriblerConfig
from tribler_core.start_core import CONFIG_FILE_NAME
from tribler_core.upgrade.upgrade import TriblerUpgrader
from tribler_core.utilities.path_util import Path


def upgrade_state_dir(root_state_dir: Path,
                      update_status_callback=None,
                      interrupt_upgrade_event=None):
    # Before any upgrade, prepare a separate state directory for the update version so it does not
    # affect the older version state directory. This allows for safe rollback.
    version_history = VersionHistory(root_state_dir)
    version_history.fork_state_directory_if_necessary()
    version_history.save_if_necessary()
    state_dir = version_history.code_version.directory
    if not state_dir.exists():
        return

    config = TriblerConfig.load(file=state_dir / CONFIG_FILE_NAME, state_dir=state_dir, reset_config_on_error=True)
    channels_dir = config.chant.get_path_as_absolute('channels_dir', config.state_dir)

    primary_private_key_path = config.state_dir / KeyComponent.get_private_key_filename(config)
    primary_public_key_path = config.state_dir / config.trustchain.ec_keypair_pubfilename
    primary_key = KeyComponent.load_or_create(primary_private_key_path, primary_public_key_path)

    upgrader = TriblerUpgrader(state_dir, channels_dir, primary_key,
                               update_status_callback=update_status_callback,
                               interrupt_upgrade_event=interrupt_upgrade_event)
    upgrader.run()


if __name__ == "__main__":
    def print_text(text):
        print(text)

    event = UpgradeInterruptedEvent()

    def interrupt_upgrade():
        event.interrupted = True

    signal.signal(signal.SIGINT, interrupt_upgrade)
    signal.signal(signal.SIGTERM, interrupt_upgrade)

    upgrade_state_dir(Path(sys.argv[1]),
                      interrupt_upgrade_event=event,
                      update_status_callback=print_text)
