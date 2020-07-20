from binascii import unhexlify

from anydex.wallet.tc_wallet import TrustchainWallet

from ipv8.attestation.trustchain.block import TrustChainBlock
from ipv8.attestation.trustchain.community import TrustChainCommunity
from ipv8.messaging.deprecated.encoding import encode
from ipv8.test.mocking.ipv8 import MockIPv8

import pytest

from tribler_core.restapi.base_api_test import do_request
from tribler_core.utilities.unicode import hexlify


@pytest.fixture
async def mock_ipv8(session):
    mock_ipv8 = MockIPv8("low", TrustChainCommunity, working_directory=session.config.get_state_dir())
    session.trustchain_community = mock_ipv8.overlay
    session.wallets['MB'] = TrustchainWallet(session.trustchain_community)
    yield mock_ipv8
    await mock_ipv8.unload()


@pytest.mark.asyncio
async def test_get_statistics_no_community(enable_api, session):
    """
    Testing whether the API returns error 404 if no trustchain community is loaded
    """
    await do_request(session, 'trustchain/statistics', expected_code=404)


@pytest.mark.asyncio
async def test_get_statistics(enable_api, mock_ipv8, session):
    """
    Testing whether the API returns the correct statistics
    """
    block = TrustChainBlock()
    block.public_key = session.trustchain_community.my_peer.public_key.key_to_bin()
    block.link_public_key = unhexlify(b"deadbeef")
    block.link_sequence_number = 21
    block.type = b'tribler_bandwidth'
    block.transaction = {b"up": 42, b"down": 8, b"total_up": 1024,
                         b"total_down": 2048, b"type": b"tribler_bandwidth"}
    block._transaction = encode(block.transaction)
    block.sequence_number = 3
    block.previous_hash = unhexlify(b"babecafe")
    block.signature = unhexlify(b"babebeef")
    block.hash = block.calculate_hash()
    session.trustchain_community.persistence.add_block(block)

    response_dict = await do_request(session, 'trustchain/statistics', expected_code=200)
    assert "statistics" in response_dict
    stats = response_dict["statistics"]
    assert stats["id"] == hexlify(session.trustchain_community.my_peer.public_key.key_to_bin())
    assert stats["total_blocks"] == 3
    assert stats["total_up"] == 1024
    assert stats["total_down"] == 2048
    assert stats["peers_that_pk_helped"] == 1
    assert stats["peers_that_helped_pk"] == 1


@pytest.mark.asyncio
async def test_get_statistics_no_data(enable_api, mock_ipv8, session):
    """
    Testing whether the API returns the correct statistics
    """
    response_dict = await do_request(session, 'trustchain/statistics', expected_code=200)
    assert "statistics" in response_dict
    stats = response_dict["statistics"]
    assert stats["id"] == hexlify(session.trustchain_community.my_peer.public_key.key_to_bin())
    assert stats["total_blocks"] == 0
    assert stats["total_up"] == 0
    assert stats["total_down"] == 0
    assert stats["peers_that_pk_helped"] == 0
    assert stats["peers_that_helped_pk"] == 0
    assert "latest_block" not in stats


@pytest.mark.asyncio
async def test_get_bootstrap_identity_no_community(enable_api, session):
    """
    Testing whether the API returns error 404 if no trustchain community is loaded when bootstrapping a new identity
    """
    await do_request(session, 'trustchain/bootstrap', expected_code=404)


@pytest.mark.asyncio
async def test_get_bootstrap_identity_all_tokens(enable_api, mock_ipv8, session):
    """
    Testing whether the API return all available tokens when no argument is supplied
    """
    transaction = {b'up': 100, b'down': 0, b'total_up': 100, b'total_down': 0}
    transaction2 = {'up': 100, 'down': 0}

    test_block = TrustChainBlock()
    test_block.type = b'tribler_bandwidth'
    test_block.transaction = transaction
    test_block._transaction = encode(transaction)
    test_block.public_key = session.trustchain_community.my_peer.public_key.key_to_bin()
    test_block.hash = test_block.calculate_hash()
    session.trustchain_community.persistence.add_block(test_block)

    response_dict = await do_request(session, 'trustchain/bootstrap', expected_code=200)
    assert response_dict['transaction'] == transaction2


@pytest.mark.asyncio
async def test_get_bootstrap_identity_partial_tokens(enable_api, mock_ipv8, session):
    """
    Testing whether the API return partial available credit when argument is supplied
    """
    transaction = {b'up': 100, b'down': 0, b'total_up': 100, b'total_down': 0}
    transaction2 = {'up': 50, 'down': 0}

    test_block = TrustChainBlock()
    test_block.type = b'tribler_bandwidth'
    test_block.transaction = transaction
    test_block._transaction = encode(transaction)
    test_block.public_key = session.trustchain_community.my_peer.public_key.key_to_bin()
    test_block.hash = test_block.calculate_hash()
    session.trustchain_community.persistence.add_block(test_block)

    response_dict = await do_request(session, 'trustchain/bootstrap?amount=50', expected_code=200)
    assert response_dict['transaction'] == transaction2


@pytest.mark.asyncio
async def test_get_bootstrap_identity_not_enough_tokens(enable_api, mock_ipv8, session):
    """
    Testing whether the API returns error 400 if bandwidth is to low when bootstrapping a new identity
    """
    transaction = {b'up': 100, b'down': 0, b'total_up': 100, b'total_down': 0}
    test_block = TrustChainBlock()
    test_block.type = b'tribler_bandwidth'
    test_block.transaction = transaction
    test_block._transaction = encode(transaction)
    test_block.public_key = session.trustchain_community.my_peer.public_key.key_to_bin()
    test_block.hash = test_block.calculate_hash()
    session.trustchain_community.persistence.add_block(test_block)

    await do_request(session, 'trustchain/bootstrap?amount=200', expected_code=400)


@pytest.mark.asyncio
async def test_get_bootstrap_identity_not_enough_tokens_2(enable_api, mock_ipv8, session):
    """
    Testing whether the API returns error 400 if bandwidth is to low when bootstrapping a new identity
    """
    transaction = {b'up': 0, b'down': 100, b'total_up': 0, b'total_down': 100}
    test_block = TrustChainBlock()
    test_block.type = b'tribler_bandwidth'
    test_block.transaction = transaction
    test_block._transaction = encode(transaction)
    test_block.public_key = session.trustchain_community.my_peer.public_key.key_to_bin()
    test_block.hash = test_block.calculate_hash()
    session.trustchain_community.persistence.add_block(test_block)

    await do_request(session, 'trustchain/bootstrap?amount=10', expected_code=400)


@pytest.mark.asyncio
async def test_get_bootstrap_identity_zero_amount(enable_api, mock_ipv8, session):
    """
    Testing whether the API returns error 400 if amount is zero when bootstrapping a new identity
    """
    await do_request(session, 'trustchain/bootstrap?amount=0', expected_code=400)


@pytest.mark.asyncio
async def test_get_bootstrap_identity_negative_amount(enable_api, mock_ipv8, session):
    """
    Testing whether the API returns error 400 if amount is negative when bootstrapping a new identity
    """
    await do_request(session, 'trustchain/bootstrap?amount=-1', expected_code=400)


@pytest.mark.asyncio
async def test_get_bootstrap_identity_string(enable_api, mock_ipv8, session):
    """
    Testing whether the API returns error 400 if amount is string when bootstrapping a new identity
    """
    await do_request(session, 'trustchain/bootstrap?amount=aaa', expected_code=400)
