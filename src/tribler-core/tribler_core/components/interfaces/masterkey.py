from unittest.mock import Mock

from ipv8.keyvault.private.libnaclkey import LibNaCLSK
from tribler_core.components.base import Component, testcomponent


class MasterKeyComponent(Component):
    enable_in_gui_test_mode = True

    keypair: LibNaCLSK


@testcomponent
class MasterKeyComponentMock(MasterKeyComponent):
    keypair = Mock()
