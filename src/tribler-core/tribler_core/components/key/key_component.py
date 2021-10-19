from ipv8.keyvault.private.libnaclkey import LibNaCLSK
from tribler_core.components.base import Component
from tribler_core.config.tribler_config import TriblerConfig
from tribler_core.utilities.path_util import Path


class KeyComponent(Component):
    # This is the primary key that is used by default, e.g., in IPv8 communities.
    primary_key: LibNaCLSK

    # This secondary key can be used as a secondary identity when it is undesirable to use
    # the primary key for privacy considerations.
    secondary_key: LibNaCLSK

    async def run(self):
        config = self.session.config

        # primary key:
        primary_private_key_path = config.state_dir / self.get_private_key_filename(config)
        primary_public_key_path = config.state_dir / config.trustchain.ec_keypair_pubfilename
        self.primary_key = self.load_or_create(primary_private_key_path, primary_public_key_path)

        # secondary key:
        secondary_private_key_path = config.state_dir / config.trustchain.secondary_key_filename
        self.secondary_key = self.load_or_create(secondary_private_key_path)

    @staticmethod
    def load_or_create(private_key_path: Path, public_key_path: Path = None) -> LibNaCLSK:
        if private_key_path.exists():
            return LibNaCLSK(private_key_path.read_bytes())

        key = LibNaCLSK()
        private_key_path.write_bytes(key.key.sk + key.key.seed)
        if public_key_path:
            public_key_path.write_bytes(key.key.pk)
        return key

    @staticmethod
    def get_private_key_filename(config: TriblerConfig):
        if config.general.testnet:
            return config.trustchain.testnet_keypair_filename

        return config.trustchain.ec_keypair_filename
