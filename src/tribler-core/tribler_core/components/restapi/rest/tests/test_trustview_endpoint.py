import random
import secrets
from binascii import unhexlify

from aiohttp.web_app import Application

from ipv8.keyvault.crypto import default_eccrypto

import pytest

from tribler_core.components.bandwidth_accounting.db.database import BandwidthDatabase
from tribler_core.components.bandwidth_accounting.db.transaction import BandwidthTransactionData, EMPTY_SIGNATURE
from tribler_core.components.bandwidth_accounting.trust_calculation.trust_graph import TrustGraph
from tribler_core.components.restapi.rest.base_api_test import do_request
from tribler_core.components.restapi.rest.rest_manager import error_middleware
from tribler_core.components.restapi.rest.trustview_endpoint import TrustViewEndpoint
from tribler_core.exceptions import TrustGraphException
from tribler_core.utilities.utilities import MEMORY_DB


@pytest.fixture
def endpoint():
    endpoint = TrustViewEndpoint()
    return endpoint


@pytest.fixture
def rest_api(loop, aiohttp_client, endpoint):  # pylint: disable=unused-argument
    app = Application(middlewares=[error_middleware])
    app.add_subapp('/trustview', endpoint.app)
    return loop.run_until_complete(aiohttp_client(app))


@pytest.fixture
def root_key():
    return default_eccrypto.generate_key("very-low").pub().key_to_bin()


@pytest.fixture
def mock_bandwidth_community(mock_ipv8, rest_api):
    return rest_api.bandwidth_community


@pytest.fixture
async def bandwidth_db(root_key):
    bandwidth_db = BandwidthDatabase(MEMORY_DB, root_key)
    return bandwidth_db


@pytest.fixture
async def trust_graph(root_key, bandwidth_db):
    return TrustGraph(root_key, bandwidth_db, max_nodes=20, max_transactions=200)


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
    test_node1_key = default_eccrypto.generate_key("very-low").pub().key_to_bin()
    test_node1 = trust_graph.get_or_create_node(test_node1_key)
    assert test_node1

    # check that node is added by default if not available in the graph
    assert len(trust_graph.node_public_keys) >= 2

    # Get node without adding to the graph
    test_node2_key = default_eccrypto.generate_key("very-low").pub().key_to_bin()
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
        test_node_key = default_eccrypto.generate_key("very-low").pub().key_to_bin()
        test_node = trust_graph.get_or_create_node(test_node_key)
        assert test_node

    assert len(trust_graph.node_public_keys) == trust_graph.max_nodes

    # If we try to add more than MAX_PEERS, we expect to get an exception
    try:
        test_node_key = default_eccrypto.generate_key("very-low").pub().key_to_bin()
        trust_graph.get_or_create_node(test_node_key)
    except TrustGraphException as tge:
        exception_msg = getattr(tge, 'message', repr(tge))
        assert f'Max node peers ({trust_graph.max_nodes}) reached in the graph' in exception_msg
    else:
        assert False, "Expected to fail but did not."


def test_add_bandwidth_transactions(trust_graph):
    """
    Tests the maximum blocks/transactions that be be present in the graph.
    :return:
    """

    my_pk = trust_graph.root_key
    for _ in range(trust_graph.max_nodes - 1):
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
        assert f'Max node peers ({trust_graph.max_nodes}) reached in the graph' in exception_msg
    else:
        assert False, "Expected to fail but did not."


async def test_trustview_response(rest_api, root_key, bandwidth_db, endpoint):
    """
    Test whether the trust graph response is correctly returned.

    Scenario: A graph with 3 nodes in each layers (layer 1: friends, layer 2: fofs, layer 3: fofofs).
    The current implementation of trust graph only considers two layers, therefore,
    number of nodes in the graph = 1 (root node) + 3 (friends) + 3 (fofs) = 7
    number of transactions in the graphs = 3 (root node to friends) + 3 (friends) * 3 (fofs) = 12
    """

    endpoint.bandwidth_db = bandwidth_db
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
        bandwidth_db.BandwidthTransaction.insert(tx1)

    for friend in friends:
        for fof in fofs:
            tx2 = BandwidthTransactionData(1, unhexlify(friend), unhexlify(fof), EMPTY_SIGNATURE, EMPTY_SIGNATURE, 3000)
            bandwidth_db.BandwidthTransaction.insert(tx2)

    for fof in fofs:
        for fofof in fofofs:
            tx3 = BandwidthTransactionData(1, unhexlify(fof), unhexlify(fofof), EMPTY_SIGNATURE, EMPTY_SIGNATURE, 3000)
            bandwidth_db.BandwidthTransaction.insert(tx3)

    response = await do_request(rest_api, 'trustview', expected_code=200)
    verify_response(response)


def insert_node_transactions(root_key, bandwidth_db, node_public_key=None, count=1):
    for idx in range(count):
        counterparty = unhexlify(node_public_key if node_public_key else get_random_node_public_key())
        amount = random.randint(10, 100)
        tx1 = BandwidthTransactionData(idx, root_key, counterparty, EMPTY_SIGNATURE, EMPTY_SIGNATURE, amount)
        bandwidth_db.BandwidthTransaction.insert(tx1)


async def test_trustview_max_transactions(rest_api, bandwidth_db, root_key, endpoint):
    """
    Test whether the max transactions returned is limited.
    """
    endpoint.bandwidth_db = bandwidth_db

    max_txn = 10
    endpoint.trust_graph.set_limits(max_transactions=max_txn)

    # Try adding more transactions than max transactions
    insert_node_transactions(root_key, bandwidth_db, count=max_txn + 1)

    # The number of transactions should not be returned more than max transactions
    response_json = await do_request(rest_api, 'trustview?refresh=1', expected_code=200)
    assert response_json['graph']
    assert response_json['num_tx'] == max_txn


async def test_trustview_max_nodes(rest_api, root_key, bandwidth_db, endpoint):
    """
    Test whether the number of nodes returned is limited.
    """
    endpoint.bandwidth_db = bandwidth_db

    max_nodes = 10
    endpoint.trust_graph.set_limits(max_nodes=max_nodes)

    # Try transactions from more than max nodes
    for _ in range(max_nodes):
        insert_node_transactions(root_key, bandwidth_db)

    # The number of nodes should not be returned more than max nodes
    response_json = await do_request(rest_api, 'trustview?refresh=1', expected_code=200)
    assert response_json['graph']
    assert len(response_json['graph']['node']) == max_nodes


async def test_trustview_with_refresh(rest_api, root_key, bandwidth_db, endpoint):
    """
    Test whether refresh query parameters works as expected.
    If refresh parameter is not set, the cached graph is returned otherwise
    a new graph is computed and returned.
    """
    endpoint.bandwidth_db = bandwidth_db

    # Insert a set of transactions
    num_tx_set1 = 10
    insert_node_transactions(root_key, bandwidth_db, count=num_tx_set1)

    # Since graph is not computed yet, freshly computed result is displayed
    # so the number of transactions returned should be equal to above number
    # of transactions added.
    response_json = await do_request(rest_api, 'trustview', expected_code=200)
    assert response_json['graph']
    assert response_json['num_tx'] == num_tx_set1

    # Now insert a second set of transactions
    num_tx_set2 = 10
    insert_node_transactions(root_key, bandwidth_db, count=num_tx_set2)

    # At this point, the trust graph should already be computed from the previous API call,
    # since the refresh parameter is not set, the cached result should be returned
    # which is same as the previous result.
    response_json = await do_request(rest_api, 'trustview', expected_code=200)
    assert response_json['graph']
    assert response_json['num_tx'] == num_tx_set1

    # Now if the refresh parameter is set, the graph should be freshly computed and all the
    # transactions should be included. Therefore, showing the correct number of transactions.
    response_json = await do_request(rest_api, 'trustview?refresh=1', expected_code=200)
    assert response_json['graph']
    assert num_tx_set1 <= response_json['num_tx'] == num_tx_set1 + num_tx_set2
