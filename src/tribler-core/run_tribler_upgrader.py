import sys

from tribler_core.components.key.key_component import KeyComponent
from tribler_core.config.tribler_config import TriblerConfig
from tribler_core.start_core import CONFIG_FILE_NAME
from tribler_core.upgrade.upgrade import TriblerUpgrader
from tribler_core.utilities.path_util import Path


def upgrade_state_dir(state_dir: Path):
    config = TriblerConfig.load(file=state_dir / CONFIG_FILE_NAME, state_dir=state_dir, reset_config_on_error=True)
    channels_dir = config.chant.get_path_as_absolute('channels_dir', config.state_dir)

    primary_private_key_path = config.state_dir / KeyComponent.get_private_key_filename(config)
    primary_public_key_path = config.state_dir / config.trustchain.ec_keypair_pubfilename
    primary_key = KeyComponent.load_or_create(primary_private_key_path, primary_public_key_path)

    upgrader = TriblerUpgrader(state_dir, channels_dir, primary_key)
    upgrader.run()


if __name__ == "__main__":
    state_dir = Path(sys.argv[1])
    upgrade_state_dir(state_dir)
