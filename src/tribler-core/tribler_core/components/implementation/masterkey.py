from unittest.mock import Mock

import tribler_core.utilities.permid as permid_module
from ipv8.keyvault.private.libnaclkey import LibNaCLSK
from tribler_core.components.base import Component, testcomponent


class MasterKeyComponent(Component):
    keypair: LibNaCLSK


class MasterKeyComponentImp(MasterKeyComponent):

    async def run(self):
        config = self.session.config
        if not config.general.testnet:
            keypair_filename = config.trustchain.ec_keypair_filename
        else:
            keypair_filename = config.trustchain.testnet_keypair_filename
        self.keypair = self.init_keypair(config.state_dir, keypair_filename)

    def init_keypair(self, state_dir, keypair_filename):
        """
        Set parameters that depend on state_dir.
        """
        keypair_path = state_dir / keypair_filename
        if keypair_path.exists():
            return permid_module.read_keypair_trustchain(keypair_path)

        trustchain_keypair = permid_module.generate_keypair_trustchain()

        # Save keypair
        trustchain_pubfilename = state_dir / 'ecpub_multichain.pem'
        permid_module.save_keypair_trustchain(trustchain_keypair, keypair_path)
        permid_module.save_pub_key_trustchain(trustchain_keypair, trustchain_pubfilename)
        return trustchain_keypair


@testcomponent
class MasterKeyComponentMock(MasterKeyComponent):
    keypair = Mock()
