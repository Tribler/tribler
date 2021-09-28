from pathlib import Path

from pydantic import BaseModel

from tribler_common.simpledefs import STATEDIR_CHANNELS_DIR


class MetadataStoreConfig(BaseModel):
    enabled: bool = True
    manager_enabled: bool = True
    channels_dir: Path = Path(STATEDIR_CHANNELS_DIR)
    testnet: bool = True

    class Config:
        validate_assignment = True
