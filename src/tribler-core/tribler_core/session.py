"""
Author(s): Vadim Bulavintsev
"""
import logging
import os
import sys
from asyncio import Event
from dataclasses import dataclass, field
from typing import List, Optional

import tribler_core.utilities.permid as permid_module
from tribler_common.simpledefs import (
    NTFY,
    STATEDIR_CHANNELS_DIR,
    STATEDIR_DB_DIR,
)
from tribler_core.config.tribler_config import TriblerConfig
from tribler_core.modules.component import Component
from tribler_core.notifier import Notifier
from tribler_core.utilities.crypto_patcher import patch_crypto_be_discovery
from tribler_core.utilities.install_dir import get_lib_path


@dataclass
class Mediator:
    # mandatory parameters
    config: TriblerConfig
    notifier: Optional[Notifier] = None
    trustchain_keypair = None

    # optional parameters (stored as dictionary)
    optional: dict = field(default_factory=dict)


def create_state_directory_structure(state_dir):
    """Create directory structure of the state directory."""

    def create_dir(path):
        if not path.is_dir():
            os.makedirs(path)

    def create_in_state_dir(path):
        create_dir(state_dir / path)

    create_dir(state_dir)
    create_in_state_dir(STATEDIR_DB_DIR)
    create_in_state_dir(STATEDIR_CHANNELS_DIR)


def init_keypair(state_dir, keypair_filename):
    """
    Set parameters that depend on state_dir.
    """
    keypair_path = state_dir / keypair_filename
    if keypair_path.exists():
        return permid_module.read_keypair_trustchain(keypair_path)
    else:
        trustchain_keypair = permid_module.generate_keypair_trustchain()

        # Save keypair
        trustchain_pubfilename = state_dir / 'ecpub_multichain.pem'
        permid_module.save_keypair_trustchain(trustchain_keypair, keypair_path)
        permid_module.save_pub_key_trustchain(trustchain_keypair, trustchain_pubfilename)
        return trustchain_keypair


async def core_session(
        config: TriblerConfig,
        components: List[Component],
        shutdown_event=Event(),
        notifier=Notifier()
):
    mediator = Mediator(config=config, notifier=notifier, optional={'shutdown_event': shutdown_event})

    logger = logging.getLogger("Session")

    patch_crypto_be_discovery()

    logger.info("Session is using state directory: %s", config.state_dir)
    create_state_directory_structure(config.state_dir)
    keypair_filename = config.trustchain.ec_keypair_filename if not config.general.testnet else config.trustchain.testnet_keypair_filename
    trustchain_keypair = init_keypair(config.state_dir, keypair_filename)
    mediator.trustchain_keypair = trustchain_keypair

    # On Mac, we bundle the root certificate for the SSL validation since Twisted is not using the root
    # certificates provided by the system trust store.
    if sys.platform == 'darwin':
        os.environ['SSL_CERT_FILE'] = str(get_lib_path() / 'root_certs_mac.pem')

    for component in components:
        await component.run(mediator)


    notifier.notify(NTFY.TRIBLER_STARTED, trustchain_keypair.key.pk)

    # If there is a config error, report to the user via GUI notifier
    if config.error:
        notifier.notify(NTFY.REPORT_CONFIG_ERROR, config.error)

    # SHUTDOWN
    await shutdown_event.wait()

    # Indicates we are shutting down core. With this environment variable set
    # to 'TRUE', RESTManager will no longer accepts any new requests.
    os.environ['TRIBLER_SHUTTING_DOWN'] = "TRUE"

    for component in components:
        await component.shutdown(mediator)

    if not config.core_test_mode:
        notifier.notify_shutdown_state("Saving configuration...")
        config.write()
