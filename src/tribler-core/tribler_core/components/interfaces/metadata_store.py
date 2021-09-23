from unittest.mock import Mock

from tribler_core.components.base import Component, testcomponent
from tribler_core.modules.metadata_store.store import MetadataStore


class MetadataStoreComponent(Component):
    enable_in_gui_test_mode = True

    mds: MetadataStore


@testcomponent
class MetadataStoreComponentMock(MetadataStoreComponent):
    mds = Mock()
