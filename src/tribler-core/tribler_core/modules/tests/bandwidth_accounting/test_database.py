from pathlib import Path

from ipv8.keyvault.crypto import default_eccrypto

from pony.orm import db_session

import pytest

from tribler_core.modules.bandwidth_accounting import EMPTY_SIGNATURE
from tribler_core.modules.bandwidth_accounting.database import BandwidthDatabase
from tribler_core.modules.bandwidth_accounting.transaction import BandwidthTransactionData


@pytest.fixture
def my_key():
    return default_eccrypto.generate_key('curve25519')


@pytest.fixture
def bandwidth_db(tmpdir, my_key):
    db = BandwidthDatabase(Path(":memory:"), my_key.pub().key_to_bin())
    yield db
    db.shutdown()


@db_session
def test_add_transaction(bandwidth_db):
    tx1 = BandwidthTransactionData(1, b"a", b"b", EMPTY_SIGNATURE, EMPTY_SIGNATURE, 3000)
    bandwidth_db.BandwidthTransaction.insert(tx1)
    tx2 = BandwidthTransactionData(1, b"a", b"b", EMPTY_SIGNATURE, EMPTY_SIGNATURE, 4000)
    bandwidth_db.BandwidthTransaction.insert(tx2)

    latest_tx = bandwidth_db.get_latest_transaction(b"a", b"b")
    assert latest_tx
    assert latest_tx.amount == 4000


@db_session
def test_get_latest_transaction(bandwidth_db):
    assert not bandwidth_db.get_latest_transaction(b"a", b"b")
    tx1 = BandwidthTransactionData(1, b"a", b"b", EMPTY_SIGNATURE, EMPTY_SIGNATURE, 3000)
    bandwidth_db.BandwidthTransaction.insert(tx1)

    tx2 = bandwidth_db.get_latest_transaction(b"a", b"b")
    assert tx1 == tx2
    assert tx2.amount == 3000


@db_session
def test_store_large_transaction(bandwidth_db):
    large_tx = BandwidthTransactionData(1, b"a", b"b", EMPTY_SIGNATURE, EMPTY_SIGNATURE, 1024 * 1024 * 1024 * 3)
    bandwidth_db.BandwidthTransaction.insert(large_tx)

    latest_tx = bandwidth_db.get_latest_transaction(b"a", b"b")
    assert latest_tx


@pytest.mark.asyncio
async def test_totals(bandwidth_db):
    with db_session:
        tx1 = BandwidthTransactionData(1, b"a", b"b", EMPTY_SIGNATURE, EMPTY_SIGNATURE, 3000)
        bandwidth_db.BandwidthTransaction.insert(tx1)

        assert bandwidth_db.get_total_taken(b"a") == 3000
        assert bandwidth_db.get_total_given(b"a") == 0

        tx2 = BandwidthTransactionData(1, b"b", b"a", EMPTY_SIGNATURE, EMPTY_SIGNATURE, 4000)
        bandwidth_db.BandwidthTransaction.insert(tx2)

    assert bandwidth_db.get_total_taken(b"a") == 3000
    assert bandwidth_db.get_total_given(b"a") == 4000
    assert bandwidth_db.get_balance(b"a") == 1000
    assert bandwidth_db.get_balance(b"b") == -1000


@db_session
def test_peers_helped(bandwidth_db):
    assert bandwidth_db.get_num_peers_helped(b"a") == 0
    tx1 = BandwidthTransactionData(1, b"a", b"b", EMPTY_SIGNATURE, EMPTY_SIGNATURE, 3000)
    bandwidth_db.BandwidthTransaction.insert(tx1)
    assert bandwidth_db.get_num_peers_helped(b"a") == 1
    tx2 = BandwidthTransactionData(2, b"a", b"c", EMPTY_SIGNATURE, EMPTY_SIGNATURE, 3000)
    bandwidth_db.BandwidthTransaction.insert(tx2)
    assert bandwidth_db.get_num_peers_helped(b"a") == 2
    tx3 = BandwidthTransactionData(1, b"b", b"c", EMPTY_SIGNATURE, EMPTY_SIGNATURE, 3000)
    bandwidth_db.BandwidthTransaction.insert(tx3)
    assert bandwidth_db.get_num_peers_helped(b"a") == 2


@db_session
def test_peers_helped_by(bandwidth_db):
    assert bandwidth_db.get_num_peers_helped_by(b"a") == 0
    tx1 = BandwidthTransactionData(1, b"b", b"a", EMPTY_SIGNATURE, EMPTY_SIGNATURE, 3000)
    bandwidth_db.BandwidthTransaction.insert(tx1)
    assert bandwidth_db.get_num_peers_helped_by(b"a") == 1
    tx2 = BandwidthTransactionData(2, b"c", b"a", EMPTY_SIGNATURE, EMPTY_SIGNATURE, 3000)
    bandwidth_db.BandwidthTransaction.insert(tx2)
    assert bandwidth_db.get_num_peers_helped_by(b"a") == 2
    tx3 = BandwidthTransactionData(1, b"c", b"b", EMPTY_SIGNATURE, EMPTY_SIGNATURE, 3000)
    bandwidth_db.BandwidthTransaction.insert(tx3)
    assert bandwidth_db.get_num_peers_helped_by(b"a") == 2


@db_session
def test_history(bandwidth_db):
    assert not bandwidth_db.get_history()
    tx1 = BandwidthTransactionData(1, bandwidth_db.my_pub_key, b"a", EMPTY_SIGNATURE, EMPTY_SIGNATURE, 3000)
    bandwidth_db.BandwidthTransaction.insert(tx1)

    history = bandwidth_db.get_history()
    assert len(history) == 1
    assert history[0]["balance"] == -3000

    tx2 = BandwidthTransactionData(1, b"a", bandwidth_db.my_pub_key, EMPTY_SIGNATURE, EMPTY_SIGNATURE, 4000)
    bandwidth_db.BandwidthTransaction.insert(tx2)

    history = bandwidth_db.get_history()
    assert len(history) == 2
    assert history[1]["balance"] == 1000

    # Test whether the history is pruned correctly
    bandwidth_db.MAX_HISTORY_ITEMS = 2
    tx3 = BandwidthTransactionData(1, b"a", bandwidth_db.my_pub_key, EMPTY_SIGNATURE, EMPTY_SIGNATURE, 2000)
    bandwidth_db.BandwidthTransaction.insert(tx3)

    history = bandwidth_db.get_history()
    assert len(history) == 2
