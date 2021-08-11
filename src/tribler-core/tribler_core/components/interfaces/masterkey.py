from unittest.mock import Mock

from tribler_core.components.base import Component, testcomponent
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
        if enable:
            from tribler_core.components.implementation.masterkey import MasterKeyComponentImp  # pylint: disable=import-outside-toplevel
            return MasterKeyComponentImp(cls)
        return MasterKeyComponentMock(cls)

@testcomponent
class MasterKeyComponentMock(MasterKeyComponent):
    keypair = Mock()
