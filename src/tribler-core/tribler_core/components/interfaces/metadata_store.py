from tribler_core.components.base import Component
from tribler_core.modules.metadata_store.store import MetadataStore


class MetadataStoreComponent(Component):
    mds: MetadataStore
