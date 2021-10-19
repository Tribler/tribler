from pydantic import Field

from tribler_core.config.tribler_config_section import TriblerConfigSection


# pylint: disable=no-self-argument


class TrustchainSettings(TriblerConfigSection):
    ec_keypair_filename: str = 'ec_multichain.pem'
    ec_keypair_pubfilename: str = 'ecpub_multichain.pem'
    testnet_keypair_filename: str = 'ec_trustchain_testnet.pem'
    secondary_key_filename: str = 'secondary_key.pem'
    testnet: bool = Field(default=False, env='TRUSTCHAIN_TESTNET')
