from unittest.mock import Mock

from tribler_core.config.tribler_config import TriblerConfig
from tribler_core.modules.ipv8_module_catalog import IPv8DiscoveryCommunityLauncher, get_hiddenimports


def test_hiddenimports():
    """
    Check if all hidden imports are detected
    """
    assert not get_hiddenimports()


def test_bootstrap_override():
    """
    Check that the DiscoveryCommunityLauncher respects the bootstrap override.
    """
    session = Mock()
    session.config = TriblerConfig()
    session.config.ipv8.bootstrap_override = "1.2.3.4:5"

    bootstrappers = IPv8DiscoveryCommunityLauncher().get_bootstrappers(session)

    assert len(bootstrappers) == 1
    assert len(bootstrappers[0][1]['dns_addresses']) == 0
    assert len(bootstrappers[0][1]['ip_addresses']) == 1
    assert ("1.2.3.4", 5) in bootstrappers[0][1]['ip_addresses']
