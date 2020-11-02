import random
import secrets
from binascii import unhexlify
from unittest.mock import Mock

from ipv8.keyvault.crypto import default_eccrypto
from ipv8.test.mocking.ipv8 import MockIPv8
from ipv8.util import succeed

import pytest

from tribler_core.exceptions import TrustGraphException
from tribler_core.modules.bandwidth_accounting import EMPTY_SIGNATURE
from tribler_core.modules.bandwidth_accounting.community import BandwidthAccountingCommunity
from tribler_core.modules.bandwidth_accounting.transaction import BandwidthTransactionData
from tribler_core.modules.trust_calculation.trust_graph import TrustGraph
from tribler_core.restapi.base_api_test import do_request


@pytest.fixture
def root_key():
    return default_eccrypto.generate_key(u"very-low").pub().key_to_bin()


@pytest.fixture
async def mock_ipv8(session):
    db_path = session.config.get_state_dir() / "bandwidth.db"
    mock_ipv8 = MockIPv8("low", BandwidthAccountingCommunity, database_path=db_path)
    session.bandwidth_community = mock_ipv8.overlay
    yield mock_ipv8
    await mock_ipv8.stop()


@pytest.fixture
def mock_bandwidth_community(mock_ipv8, session):
    return session.bandwidth_community


@pytest.fixture
async def trust_graph(root_key, mock_bandwidth_community):
    bandwidth_db = mock_bandwidth_community.database
    return TrustGraph(root_key, bandwidth_db, max_nodes=20, max_transactions=200)


@pytest.fixture
def mock_bootstrap(session):
    session.bootstrap = Mock()
    session.bootstrap.shutdown = lambda: succeed(None)

    bootstrap_download_state = Mock()
    bootstrap_download_state.get_total_transferred = lambda _: random.randint(0, 10000)
    bootstrap_download_state.get_progress = lambda: random.randint(10, 100)

    session.bootstrap.download.get_state = lambda: bootstrap_download_state


def get_random_node_public_key():
    return secrets.token_hex(nbytes=148)


def test_initialize(trust_graph):
    """
    Tests the initialization of the Trust graph. At least root node should be in the graph.
    """
    assert len(trust_graph.node_public_keys) >= 1


def test_get_node_and_reset(root_key, trust_graph):
    """
    Tests get node with and without adding to the graph.
    Also tests the reset of the graph.
    """
    test_node1_key = default_eccrypto.generate_key(u"very-low").pub().key_to_bin()
    test_node1 = trust_graph.get_or_create_node(test_node1_key)
    assert test_node1

    # check that node is added by default if not available in the graph
    assert len(trust_graph.node_public_keys) >= 2

    # Get node without adding to the graph
    test_node2_key = default_eccrypto.generate_key(u"very-low").pub().key_to_bin()
    test_node2 = trust_graph.get_or_create_node(test_node2_key, add_if_not_exist=False)
    assert test_node2 is None

    # After resetting the graph, there should only be one root node
    trust_graph.reset(root_key)
    assert len(trust_graph.node_public_keys) == 1


def test_maximum_nodes_in_graph(trust_graph):
    """
    Tests the maximum nodes that can be present in the graph.
    """
    # Added the MAX_PEERS nodes in the graph (including the root node)
    for _ in range(trust_graph.max_nodes - 1):
        test_node_key = default_eccrypto.generate_key(u"very-low").pub().key_to_bin()
        test_node = trust_graph.get_or_create_node(test_node_key)
        assert test_node

    assert len(trust_graph.node_public_keys) == trust_graph.max_nodes

    # If we try to add more than MAX_PEERS, we expect to get an exception
    try:
        test_node_key = default_eccrypto.generate_key(u"very-low").pub().key_to_bin()
        trust_graph.get_or_create_node(test_node_key)
    except TrustGraphException as tge:
        exception_msg = getattr(tge, 'message', repr(tge))
        assert 'Max node peers reached in graph' in exception_msg
    else:
        assert False, "Expected to fail but did not."


def test_add_bandwidth_transactions(trust_graph):
    """
    Tests the maximum blocks/transactions that be be present in the graph.
    :return:
    """

    my_pk = trust_graph.root_key
    for _ in range(trust_graph.max_nodes-1):
        random_node_pk = unhexlify(get_random_node_public_key())
        random_tx = BandwidthTransactionData(1, random_node_pk, my_pk, EMPTY_SIGNATURE, EMPTY_SIGNATURE, 3000)
        trust_graph.add_bandwidth_transaction(random_tx)

    assert trust_graph.number_of_nodes() == trust_graph.max_nodes

    # Already max number of nodes are added to the graph, adding more should raise an exception
    try:
        tx2 = BandwidthTransactionData(1, my_pk, b"a", EMPTY_SIGNATURE, EMPTY_SIGNATURE, 2000)
        trust_graph.add_bandwidth_transaction(tx2)
    except TrustGraphException as tge:
        exception_msg = getattr(tge, 'message', repr(tge))
        assert 'Max node peers reached in graph' in exception_msg
    else:
        assert False, "Expected to fail but did not."


@pytest.mark.asyncio
async def test_trustview_response(enable_api, mock_ipv8, session, mock_bootstrap):
    """
    Test whether the trust graph response is correctly returned.

    Scenario: A graph with 3 nodes in each layers (layer 1: friends, layer 2: fofs, layer 3: fofofs).
    The current implementation of trust graph only considers two layers, therefore,
    number of nodes in the graph = 1 (root node) + 3 (friends) + 3 (fofs) = 7
    number of transactions in the graphs = 3 (root node to friends) + 3 (friends) * 3 (fofs) = 12
    """
    root_key = session.bandwidth_community.my_pk
    friends = [
        "4c69624e61434c504b3a2ee28ce24a2259b4e585b81106cdff4359fcf48e93336c11d133b01613f30b03b4db06df27"
        "80daac2cdf2ee60be611bf7367a9c1071ac50d65ca5858a50e9578",
        "4c69624e61434c504b3a5368c7b39a82063e29576df6d74fba3e0dba3af8e7a304b553b71f08ea6a0730e8cef767a4"
        "85dc6f390b6da5631f772941ea69ce2c098d802b7a28b500edf2b3",
        "4c69624e61434c504b3a0f3f6318e49ffeb0a160e7fcac5c1d3337ba409b45e1371ddca5e3b364ebdd1b73c775318a"
        "533a25335a5c36ae3695f1c3036b651893659fbf2e1f2bce66cf65",
    ]

    fofs = [
        "4c69624e61434c504b3a2ee28ce24a2259b4e585b81106cdff4359fcf48e93336c11d133b01613f30b03b4db06df27"
        "80daac2cdf2ee60be611bf7367a9c1071ac50d65ca5858a50e9579",
        "4c69624e61434c504b3a5368c7b39a82063e29576df6d74fba3e0dba3af8e7a304b553b71f08ea6a0730e8cef767a4"
        "85dc6f390b6da5631f772941ea69ce2c098d802b7a28b500edf2b4",
        "4c69624e61434c504b3a0f3f6318e49ffeb0a160e7fcac5c1d3337ba409b45e1371ddca5e3b364ebdd1b73c775318a"
        "533a25335a5c36ae3695f1c3036b651893659fbf2e1f2bce66cf66",
    ]

    fofofs = [
        "4c69624e61434c504b3a2ee28ce24a2259b4e585b81106cdff4359fcf48e93336c11d133b01613f30b03b4db06df27"
        "80daac2cdf2ee60be611bf7367a9c1071ac50d65ca5858a50e9580",
        "4c69624e61434c504b3a5368c7b39a82063e29576df6d74fba3e0dba3af8e7a304b553b71f08ea6a0730e8cef767a4"
        "85dc6f390b6da5631f772941ea69ce2c098d802b7a28b500edf2b5",
        "4c69624e61434c504b3a0f3f6318e49ffeb0a160e7fcac5c1d3337ba409b45e1371ddca5e3b364ebdd1b73c775318a"
        "533a25335a5c36ae3695f1c3036b651893659fbf2e1f2bce66cf67",
    ]

    def verify_response(response_json):
        expected_nodes = 1 + len(friends) + len(fofs)
        expected_txns = len(friends) + len(friends) * len(fofs)

        assert response_json['graph']
        assert response_json['num_tx'] == expected_txns
        assert len(response_json['graph']['node']) == expected_nodes

    for pub_key in friends:
        tx1 = BandwidthTransactionData(1, root_key, unhexlify(pub_key), EMPTY_SIGNATURE, EMPTY_SIGNATURE, 3000)
        session.bandwidth_community.database.BandwidthTransaction.insert(tx1)

    for friend in friends:
        for fof in fofs:
            tx2 = BandwidthTransactionData(1, unhexlify(friend), unhexlify(fof), EMPTY_SIGNATURE, EMPTY_SIGNATURE, 3000)
            session.bandwidth_community.database.BandwidthTransaction.insert(tx2)

    for fof in fofs:
        for fofof in fofofs:
            tx3 = BandwidthTransactionData(1, unhexlify(fof), unhexlify(fofof), EMPTY_SIGNATURE, EMPTY_SIGNATURE, 3000)
            session.bandwidth_community.database.BandwidthTransaction.insert(tx3)

    response = await do_request(session, 'trustview', expected_code=200)
    verify_response(response)


@pytest.mark.asyncio
async def test_trustview_max_response(enable_api, mock_ipv8, session, mock_bootstrap):
    """
    Test whether the trust graph response is limited.
    Here we redefine the max peers and max transactions limit for trust graph and add more peers and transactions,
    then test if the endpoint response is limited.
    """
    max_peers = 10
    max_tx = 10
    root_key = session.bandwidth_community.my_pk
    endpoint = session.api_manager.root_endpoint.endpoints['/trustview']
    endpoint.initialize_graph()
    endpoint.trust_graph.set_limits(max_peers, max_tx)

    for _ in range(max_peers * 2):
        random_node = unhexlify(get_random_node_public_key())
        tx1 = BandwidthTransactionData(1, root_key, random_node, EMPTY_SIGNATURE, EMPTY_SIGNATURE, 3000)
        session.bandwidth_community.database.BandwidthTransaction.insert(tx1)

    response_json = await do_request(session, 'trustview', expected_code=200)
    assert response_json['graph']
    assert response_json['num_tx'] <= max_tx
    assert len(response_json['graph']['node']) <= max_peers
