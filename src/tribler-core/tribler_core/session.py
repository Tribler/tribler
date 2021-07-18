"""
Author(s): Vadim Bulavintsev
"""
import itertools
import logging
import os
import sys
from asyncio import Event, create_task, gather, Future, get_event_loop
from dataclasses import dataclass, field
from typing import List, Optional, Dict

import tribler_core.utilities.permid as permid_module
from tribler_common.simpledefs import (
    NTFY,
    STATEDIR_CHANNELS_DIR,
    STATEDIR_DB_DIR,
)
from tribler_core.config.tribler_config import TriblerConfig
from tribler_core.mediator import Mediator
from tribler_core.modules.component import Component
from tribler_core.notifier import Notifier
from tribler_core.resource_lock import ResourceLock
from tribler_core.utilities.crypto_patcher import patch_crypto_be_discovery
from tribler_core.utilities.install_dir import get_lib_path
from tribler_core.utilities.unicode import hexlify


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
    mediator = Mediator(config=config, notifier=notifier, shutdown_event=shutdown_event)

    logger = logging.getLogger("Session")

    patch_crypto_be_discovery()

    logger.info("Session is using state directory: %s", config.state_dir)
    create_state_directory_structure(config.state_dir)

    keypair_filename = config.trustchain.ec_keypair_filename if not config.general.testnet else config.trustchain.testnet_keypair_filename
    trustchain_keypair = init_keypair(config.state_dir, keypair_filename)
    mediator.trustchain_keypair = trustchain_keypair

    from tribler_common.sentry_reporter.sentry_reporter import SentryReporter
    user_id_str = hexlify(trustchain_keypair.key.pk).encode('utf-8')
    SentryReporter.set_user(user_id_str)

    # On Mac, we bundle the root certificate for the SSL validation since Twisted is not using the root
    # certificates provided by the system trust store.
    if sys.platform == 'darwin':
        os.environ['SSL_CERT_FILE'] = str(get_lib_path() / 'root_certs_mac.pem')

    for comp in components:
        mediator.optional[comp.role] = ResourceLock()

    await gather(*[create_task(component.run(mediator)) for component in components])

    #from tribler_core.restapi.rest_manager import RESTManager
    #from ipv8_service import IPv8
    #ipv8 = await mediator.components[IPv8]
    #(await mediator.components[RESTManager]).get_endpoint('ipv8').initialize(ipv8)

    notifier.notify(NTFY.TRIBLER_STARTED, trustchain_keypair.key.pk)

    # If there is a config error, report to the user via GUI notifier
    if config.error:
        notifier.notify(NTFY.REPORT_CONFIG_ERROR, config.error)

    # SHUTDOWN
    await shutdown_event.wait()

    # Indicates we are shutting down core. With this environment variable set
    # to 'TRUE', RESTManager will no longer accepts any new requests.
    os.environ['TRIBLER_SHUTTING_DOWN'] = "TRUE"

    await gather(*[create_task(component.shutdown(mediator)) for component in components])

    if not config.core_test_mode:
        notifier.notify_shutdown_state("Saving configuration...")
        config.write()
