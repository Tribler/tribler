from dependency_injector import containers, providers

from tribler_core.modules.metadata_store.store import MetadataStore


class MetadataStoreContainer(containers.DeclarativeContainer):
    config = providers.Configuration()
    trustchain_keypair = providers.Singleton()
    notifier = providers.Singleton()

    metadata_store = providers.Singleton(
        MetadataStore,
        db_filename=config.db_filename,
        channels_dir=config.channels_dir,
        my_key=trustchain_keypair,
        notifier=notifier,
        disable_sync=config.core_test_mode,
    )
