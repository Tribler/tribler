import tribler_core.utilities.permid as permid_module


class TrustChainKeys:
    def __init__(self, config=None):
        """Extracted from session.py
        """
        keypair_filename = config.trustchain.get_path_as_absolute('ec_keypair_filename', config.state_dir)
        state_dir = config.state_dir
        if keypair_filename.exists():
            self.keypair = permid_module.read_keypair_trustchain(keypair_filename)
        else:
            self.keypair = permid_module.generate_keypair_trustchain()

            # Save keypair
            trustchain_pubfilename = state_dir / 'ecpub_multichain.pem'
            permid_module.save_keypair_trustchain(self.keypair, keypair_filename)
            permid_module.save_pub_key_trustchain(self.keypair, trustchain_pubfilename)

        testnet_keypair_filename = config.trustchain.get_path_as_absolute('testnet_keypair_filename',
                                                                          config.state_dir)
        if testnet_keypair_filename.exists():
            self.testnet_keypair = permid_module.read_keypair_trustchain(testnet_keypair_filename)
        else:
            self.testnet_keypair = permid_module.generate_keypair_trustchain()

            # Save keypair
            trustchain_testnet_pubfilename = state_dir / 'ecpub_trustchain_testnet.pem'
            permid_module.save_keypair_trustchain(self.testnet_keypair, testnet_keypair_filename)
            permid_module.save_pub_key_trustchain(self.testnet_keypair, trustchain_testnet_pubfilename)
