from unittest.mock import Mock

from tribler_core.components.base import Component, testcomponent
from tribler_core.config.tribler_config import TriblerConfig
from tribler_core.modules.metadata_store.store import MetadataStore


class MetadataStoreComponent(Component):
    enable_in_gui_test_mode = True

    mds: MetadataStore

    @classmethod
    def should_be_enabled(cls, config: TriblerConfig):
        return config.chant.enabled

    @classmethod
    def make_implementation(cls, config: TriblerConfig, enable: bool):
        if enable:
            from tribler_core.components.implementation.metadata_store import MetadataStoreComponentImp
            return MetadataStoreComponentImp()
        return MetadataStoreComponentMock()


@testcomponent
class MetadataStoreComponentMock(MetadataStoreComponent):
    mds = Mock()
