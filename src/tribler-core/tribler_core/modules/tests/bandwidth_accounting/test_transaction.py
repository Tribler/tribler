from ipv8.keyvault.crypto import default_eccrypto

from tribler_core.modules.bandwidth_accounting import EMPTY_SIGNATURE
from tribler_core.modules.bandwidth_accounting.transaction import BandwidthTransactionData


def test_sign_transaction():
    key1 = default_eccrypto.generate_key('curve25519')
    key2 = default_eccrypto.generate_key('curve25519')
    tx = BandwidthTransactionData(1, key1.pub().key_to_bin(), key2.pub().key_to_bin(),
                                  EMPTY_SIGNATURE, EMPTY_SIGNATURE, 3000)

    tx.sign(key1, as_a=True)
    assert tx.is_valid()
    assert tx.signature_a != EMPTY_SIGNATURE
    assert tx.signature_b == EMPTY_SIGNATURE

    tx.sign(key2, as_a=False)
    assert tx.is_valid()
    assert tx.signature_a != EMPTY_SIGNATURE
    assert tx.signature_b != EMPTY_SIGNATURE


def test_is_valid():
    key1 = default_eccrypto.generate_key('curve25519')
    key2 = default_eccrypto.generate_key('curve25519')
    tx = BandwidthTransactionData(1, key1.pub().key_to_bin(), key2.pub().key_to_bin(),
                                  EMPTY_SIGNATURE, EMPTY_SIGNATURE, 3000)

    assert tx.is_valid()  # No signatures have been computed so far

    tx.signature_a = b'a' * 32
    assert not tx.is_valid()

    tx.signature_a = EMPTY_SIGNATURE
    tx.signature_b = b'a' * 32
    assert not tx.is_valid()

    tx.signature_a = EMPTY_SIGNATURE
    tx.signature_b = EMPTY_SIGNATURE
    tx.sequence_number = -1
    assert not tx.is_valid()
