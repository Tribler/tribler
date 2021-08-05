from tribler_core.components.interfaces.reporter import ReporterComponent
from tribler_core.components.interfaces.trustchain import TrustchainComponent
import tribler_core.utilities.permid as permid_module


def init_keypair(state_dir, keypair_filename):
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


class TrustchainComponentImp(TrustchainComponent):
    async def run(self):
        config = self.session.config
        if not config.general.testnet:
            keypair_filename = config.trustchain.ec_keypair_filename
        else:
            keypair_filename = config.trustchain.testnet_keypair_filename
        self.keypair = init_keypair(config.state_dir, keypair_filename)

