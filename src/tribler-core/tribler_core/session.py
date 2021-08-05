"""
Author(s): Vadim Bulavintsev
"""
import logging
import os
import signal
import sys
from typing import List, Tuple, Type

from tribler_common.simpledefs import NTFY, STATEDIR_CHANNELS_DIR, STATEDIR_DB_DIR

from tribler_core.components.base import Component, Session, set_default_session
from tribler_core.components.interfaces.ipv8 import Ipv8Component
from tribler_core.components.interfaces.restapi import RESTComponent
from tribler_core.components.interfaces.trustchain import TrustchainComponent
from tribler_core.config.tribler_config import TriblerConfig
from tribler_core.utilities.crypto_patcher import patch_crypto_be_discovery
from tribler_core.utilities.install_dir import get_lib_path


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


async def core_session(
        config: TriblerConfig,
        components: List[Tuple[Type[Component], bool]]
):
    session = Session(config, components)
    signal.signal(signal.SIGTERM, lambda signum, stack: session.shutdown_event.set)
    set_default_session(session)

    logger = logging.getLogger("Session")

    patch_crypto_be_discovery()

    logger.info("Session is using state directory: %s", config.state_dir)
    create_state_directory_structure(config.state_dir)

    # On Mac, we bundle the root certificate for the SSL validation since Twisted is not using the root
    # certificates provided by the system trust store.
    if sys.platform == 'darwin':
        os.environ['SSL_CERT_FILE'] = str(get_lib_path() / 'root_certs_mac.pem')

    await session.start()

    # FIXME: workaround for IPv8 initializing all endpoints in one go
    ipv8 = Ipv8Component.imp().ipv8
    RESTComponent.imp().rest_manager.get_endpoint('ipv8').initialize(ipv8)

    session.notifier.notify(NTFY.TRIBLER_STARTED, TrustchainComponent.imp().keypair.key.pk)

    # If there is a config error, report to the user via GUI notifier
    if config.error:
        session.notifier.notify(NTFY.REPORT_CONFIG_ERROR, config.error)

    # SHUTDOWN
    await session.shutdown_event.wait()

    # Indicates we are shutting down core. With this environment variable set
    # to 'TRUE', RESTManager will no longer accept any new requests.
    os.environ['TRIBLER_SHUTTING_DOWN'] = "TRUE"

    await session.shutdown()

    if not config.core_test_mode:
        session.notifier.notify_shutdown_state("Saving configuration...")
        config.write()
