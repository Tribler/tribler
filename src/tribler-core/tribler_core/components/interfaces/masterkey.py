from tribler_core.components.base import Component
from tribler_core.config.tribler_config import TriblerConfig
from ipv8.keyvault.private.libnaclkey import LibNaCLSK

class MasterKeyComponent(Component):
    enable_in_gui_test_mode = True

    keypair: LibNaCLSK

    @classmethod
    def should_be_enabled(cls, config: TriblerConfig):
        return True

    @classmethod
    def make_implementation(cls, config: TriblerConfig, enable: bool):
        from tribler_core.components.implementation.masterkey import MasterKeyComponentImp
        return MasterKeyComponentImp(cls)
