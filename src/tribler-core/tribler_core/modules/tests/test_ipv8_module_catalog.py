from tribler_core.modules.ipv8_module_catalog import get_hiddenimports


def test_hiddenimports():
    """
    Check if all hidden imports are detected
    """
    hiddenimports = get_hiddenimports()

    assert 'ipv8.dht.churn' in hiddenimports
    assert 'ipv8.dht.discovery' in hiddenimports
    assert 'ipv8.peerdiscovery.churn' in hiddenimports
    assert 'ipv8.peerdiscovery.community' in hiddenimports
    assert 'ipv8.peerdiscovery.discovery' in hiddenimports
    assert 'tribler_core.modules.popularity.popularity_community' in hiddenimports
    assert 'tribler_core.modules.metadata_store.community.gigachannel_community' in hiddenimports
    assert 'tribler_core.modules.metadata_store.community.remote_query_community' in hiddenimports
    assert 'tribler_core.modules.metadata_store.community.sync_strategy' in hiddenimports
    assert 'tribler_core.modules.tunnel.community.discovery' in hiddenimports
    assert 'tribler_core.modules.tunnel.community.triblertunnel_community' in hiddenimports
