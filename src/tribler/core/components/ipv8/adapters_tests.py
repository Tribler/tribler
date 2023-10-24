import inspect

from ipv8.test.base import TestBase
from ipv8.test.mocking.ipv8 import MockIPv8


def backport_to_settings_class(overlay_class, kwargs):
    signature = inspect.signature(overlay_class.__init__)
    defaults = {k: v.default for k, v in signature.parameters.items()
                if v.default is not inspect.Parameter.empty}
    defaults.update(kwargs)
    return overlay_class.settings_class(**defaults)


class TriblerMockIPv8(MockIPv8):

    def __init__(self, crypto_curve_or_peer, overlay_class, create_dht = False, enable_statistics = False,
                 **kwargs):
        community_settings = backport_to_settings_class(overlay_class, kwargs)

        class ProxyOverlay(overlay_class):

            def __init__(self, settings):
                super().__init__(**settings.__dict__)

        super().__init__(crypto_curve_or_peer, ProxyOverlay, community_settings, create_dht, enable_statistics)


class TriblerTestBase(TestBase):

    def create_node(self, *args, **kwargs):
        create_dht = args[1] if len(args) > 1 else False
        enable_statistics = args[2] if len(args) > 2 else False
        return TriblerMockIPv8("low", self.overlay_class, create_dht=create_dht,
                               enable_statistics=enable_statistics, **kwargs)
