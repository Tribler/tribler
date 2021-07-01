import tribler_core.utilities.permid as permid_module
from tribler_core.utilities.path_util import Path


class TrustChainKeys:
    def __init__(self, state_dir=None, config=None):
        """Extracted from session.py
        """

        keypair_filename = Path(config.trustchain.ec_keypair_filename()).normalize_to(state_dir)
        if keypair_filename.exists():
            self.keypair = permid_module.read_keypair_trustchain(keypair_filename)
        else:
            self.keypair = permid_module.generate_keypair_trustchain()

            # Save keypair
            trustchain_pubfilename = state_dir / 'ecpub_multichain.pem'
            permid_module.save_keypair_trustchain(self.keypair, keypair_filename)
            permid_module.save_pub_key_trustchain(self.keypair, trustchain_pubfilename)

        testnet_keypair_filename = Path(config.trustchain.testnet_keypair_filename()).normalize_to(state_dir)
        if testnet_keypair_filename.exists():
            self.testnet_keypair = permid_module.read_keypair_trustchain(testnet_keypair_filename)
        else:
            self.testnet_keypair = permid_module.generate_keypair_trustchain()

            # Save keypair
            trustchain_testnet_pubfilename = state_dir / 'ecpub_trustchain_testnet.pem'
            permid_module.save_keypair_trustchain(self.testnet_keypair, testnet_keypair_filename)
            permid_module.save_pub_key_trustchain(self.testnet_keypair, trustchain_testnet_pubfilename)
