from __future__ import annotations

from ipv8.messaging.lazy_payload import VariablePayload, vp_compile


@vp_compile
class BandwidthTransactionPayload(VariablePayload):
    """
    Payload for a message containing a bandwidth transaction.
    """
    msg_id = 1
    format_list = ['I', '74s', '74s', '64s', '64s', 'Q', 'Q', 'I']
    names = ["sequence_number", "public_key_a", "public_key_b", "signature_a", "signature_b", "amount",
             "timestamp", "request_id"]

    @classmethod
    def from_transaction(cls, transaction: BandwidthTransaction, request_id: int) -> BandwidthTransactionPayload:  # noqa: F821
        return BandwidthTransactionPayload(
            transaction.sequence_number,
            transaction.public_key_a,
            transaction.public_key_b,
            transaction.signature_a,
            transaction.signature_b,
            transaction.amount,
            transaction.timestamp,
            request_id
        )


@vp_compile
class BandwidthTransactionQueryPayload(VariablePayload):
    """
    (empty) payload for an outgoing query to fetch transactions by the counterparty.
    """
    msg_id = 2
