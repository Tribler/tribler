import random

from ipv8.keyvault.crypto import default_eccrypto

from pony.orm import db_session

import pytest

from tribler_core.components.bandwidth_accounting.db.database import BandwidthDatabase
from tribler_core.components.bandwidth_accounting.db.transaction import BandwidthTransactionData, EMPTY_SIGNATURE
from tribler_core.utilities.utilities import MEMORY_DB


@pytest.fixture
def my_key():
    return default_eccrypto.generate_key('curve25519')


@pytest.fixture
def bandwidth_db(tmpdir, my_key):
    db = BandwidthDatabase(MEMORY_DB, my_key.pub().key_to_bin())
    yield db
    db.shutdown()


@db_session
def test_add_transaction(bandwidth_db):
    tx1 = BandwidthTransactionData(1, b"a", b"b", EMPTY_SIGNATURE, EMPTY_SIGNATURE, 3000)
    bandwidth_db.BandwidthTransaction.insert(tx1)
    assert bandwidth_db.has_transaction(tx1)
    tx2 = BandwidthTransactionData(2, b"a", b"b", EMPTY_SIGNATURE, EMPTY_SIGNATURE, 4000)
    bandwidth_db.BandwidthTransaction.insert(tx2)

    latest_tx = bandwidth_db.get_latest_transaction(b"a", b"b")
    assert latest_tx
    assert latest_tx.amount == 4000

    # Test storing all transactions
    bandwidth_db.store_all_transactions = True
    tx3 = BandwidthTransactionData(3, b"a", b"b", EMPTY_SIGNATURE, EMPTY_SIGNATURE, 4000)
    bandwidth_db.BandwidthTransaction.insert(tx3)
    assert len(list(bandwidth_db.BandwidthTransaction.select())) == 2
    assert bandwidth_db.has_transaction(tx2)
    assert bandwidth_db.has_transaction(tx3)

    # Test whether adding a transaction again does not result in an error
    bandwidth_db.BandwidthTransaction.insert(tx2)


@db_session
def test_get_my_latest_transactions(bandwidth_db):
    assert not bandwidth_db.get_my_latest_transactions()

    tx1 = BandwidthTransactionData(1, b"a", bandwidth_db.my_pub_key, EMPTY_SIGNATURE, EMPTY_SIGNATURE, 3000)
    bandwidth_db.BandwidthTransaction.insert(tx1)
    tx2 = BandwidthTransactionData(1, bandwidth_db.my_pub_key, b"c", EMPTY_SIGNATURE, EMPTY_SIGNATURE, 3000)
    bandwidth_db.BandwidthTransaction.insert(tx2)
    tx3 = BandwidthTransactionData(1, b"c", b"d", EMPTY_SIGNATURE, EMPTY_SIGNATURE, 3000)
    bandwidth_db.BandwidthTransaction.insert(tx3)

    assert len(bandwidth_db.get_my_latest_transactions()) == 2
    assert len(bandwidth_db.get_my_latest_transactions(limit=1)) == 1


@db_session
def test_get_latest_transaction(bandwidth_db):
    assert not bandwidth_db.get_latest_transaction(b"a", b"b")
    tx1 = BandwidthTransactionData(1, b"a", b"b", EMPTY_SIGNATURE, EMPTY_SIGNATURE, 3000)
    bandwidth_db.BandwidthTransaction.insert(tx1)

    tx2 = bandwidth_db.get_latest_transaction(b"a", b"b")
    assert tx1 == tx2
    assert tx2.amount == 3000


@db_session
def test_get_latest_transactions(bandwidth_db):
    pub_key_a = b"a"
    pub_keys_rest = [b"b", b"c", b"d", b"e", b"f"]

    assert not bandwidth_db.get_latest_transactions(pub_key_a)

    for pub_key in pub_keys_rest:
        seq_number = random.randint(1, 100)
        amount = random.randint(1, 1000)
        tx = BandwidthTransactionData(seq_number, pub_key_a, pub_key, EMPTY_SIGNATURE, EMPTY_SIGNATURE, amount)
        bandwidth_db.BandwidthTransaction.insert(tx)

    txs = bandwidth_db.get_latest_transactions(pub_key_a)
    assert len(txs) == len(pub_keys_rest)


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
