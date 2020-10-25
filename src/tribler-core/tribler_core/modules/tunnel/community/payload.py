from __future__ import annotations

from ipv8.messaging.lazy_payload import VariablePayload, vp_compile


@vp_compile
class BandwidthTransactionPayload(VariablePayload):
    """
    Payload for a message containing a bandwidth transaction.
    """
    msg_id = 30
    format_list = ['I', '74s', '74s', '64s', '64s', 'Q', 'Q', 'I', 'I']
    names = ["sequence_number", "public_key_a", "public_key_b", "signature_a", "signature_b", "amount", "timestamp",
             "circuit_id", "base_amount"]

    @classmethod
    def from_transaction(cls, transaction: BandwidthTransaction, circuit_id: int, base_amount: int):  # noqa: F821
        """
        Create a transaction from the provided payload.
        :param transaction: The transaction to convert to a payload.
        :param circuit_id: The circuit identifier to include in the payload.
        :param base_amount: The base amount of bandwidth to payout.
        """
        return BandwidthTransactionPayload(
            transaction.sequence_number,
            transaction.public_key_a,
            transaction.public_key_b,
            transaction.signature_a,
            transaction.signature_b,
            transaction.amount,
            transaction.timestamp,
            circuit_id,
            base_amount
        )


@vp_compile
class BalanceResponsePayload(VariablePayload):
    """
    Payload that contains the bandwidth balance of a specific peer.
    """
    msg_id = 31
    format_list = ["I", "q"]
    names = ["circuit_id", "balance"]


class RelayBalanceResponsePayload(BalanceResponsePayload):
    msg_id = 32


@vp_compile
class BalanceRequestPayload(VariablePayload):
    msg_id = 33
    format_list = ['I', 'H']
    names = ['circuit_id', 'identifier']


@vp_compile
class RelayBalanceRequestPayload(VariablePayload):
    msg_id = 34
    format_list = ['I']
    names = ['circuit_id']


@vp_compile
class HTTPRequestPayload(VariablePayload):
    msg_id = 28
    format_list = ['I', 'I', 'address', 'varlenH']
    names = ['circuit_id', 'identifier', 'target', 'request']


@vp_compile
class HTTPResponsePayload(VariablePayload):
    msg_id = 29
    format_list = ['I', 'I', 'H', 'H', 'varlenH']
    names = ['circuit_id', 'identifier', 'part', 'total', 'response']
