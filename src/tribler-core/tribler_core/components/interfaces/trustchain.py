from tribler_core.components.base import Component
from ipv8.keyvault.private.libnaclkey import LibNaCLSK

class TrustchainComponent(Component):
    core = True

    keypair: LibNaCLSK

    @classmethod
    def should_be_enabled(cls, config):
        return True

    @classmethod
    def make_implementation(cls, config, enable):
        from tribler_core.components.implementation.trustchain import TrustchainComponentImp
        return TrustchainComponentImp()
