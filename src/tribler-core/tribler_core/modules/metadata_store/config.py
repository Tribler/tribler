from pathlib import Path

from pydantic import BaseModel


class MetadataStoreConfig(BaseModel):
    enabled: bool = True
    manager_enabled: bool = True
    channels_dir: Path = Path('channels')
    testnet: bool = True

    class Config:
        validate_assignment = True
