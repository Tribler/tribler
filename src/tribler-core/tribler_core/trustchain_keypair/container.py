from dependency_injector import containers, providers

from tribler_core.trustchain_keypair.keypair_utils import load_keypair


class KeypairUtilsContainer(containers.DeclarativeContainer):
    keypair_filename = providers.Object()
    trustchain_pubfilename = providers.Object()
    trustchain_keypair = providers.Singleton(load_keypair,
                                             keypair_filename=keypair_filename,
                                             trustchain_pubfilename=trustchain_pubfilename)

