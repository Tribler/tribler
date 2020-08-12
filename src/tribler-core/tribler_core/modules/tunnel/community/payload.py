from ipv8.attestation.trustchain.payload import HalfBlockPayload
from ipv8.messaging.lazy_payload import VariablePayload, vp_compile


class PayoutPayload(HalfBlockPayload):
    msg_id = 23
    format_list = HalfBlockPayload.format_list + ["I", "I"]

    def __init__(self, public_key, sequence_number, link_public_key, link_sequence_number, previous_hash,
                 signature, block_type, transaction, timestamp, circuit_id, base_amount):
        super(PayoutPayload, self).__init__(public_key, sequence_number, link_public_key, link_sequence_number,
                                            previous_hash, signature, block_type, transaction, timestamp)
        self.circuit_id = circuit_id
        self.base_amount = base_amount

    @classmethod
    def from_half_block(cls, block, circuit_id, base_amount):
        return PayoutPayload(
            block.public_key,
            block.sequence_number,
            block.link_public_key,
            block.link_sequence_number,
            block.previous_hash,
            block.signature,
            block.type,
            block._transaction,
            block.timestamp,
            circuit_id,
            base_amount
        )

    def to_pack_list(self):
        data = super(PayoutPayload, self).to_pack_list()
        data.append(('I', self.circuit_id))
        data.append(('I', self.base_amount))
        return data

    @classmethod
    def from_unpack_list(cls, *args):
        return PayoutPayload(*args)


class BalanceResponsePayload(HalfBlockPayload):
    msg_id = 26
    format_list = ["I"] + HalfBlockPayload.format_list

    def __init__(self, circuit_id, public_key, sequence_number, link_public_key, link_sequence_number, previous_hash,
                 signature, block_type, transaction, timestamp):
        super(BalanceResponsePayload, self).__init__(public_key, sequence_number, link_public_key,
                                                     link_sequence_number, previous_hash, signature, block_type,
                                                     transaction, timestamp)
        self.circuit_id = circuit_id

    @classmethod
    def from_half_block(cls, block, circuit_id):
        return cls(
            circuit_id,
            block.public_key,
            block.sequence_number,
            block.link_public_key,
            block.link_sequence_number,
            block.previous_hash,
            block.signature,
            block.type,
            block._transaction,
            block.timestamp
        )

    def to_pack_list(self):
        data = super(BalanceResponsePayload, self).to_pack_list()
        data.insert(0, ('I', self.circuit_id))
        return data

    @classmethod
    def from_unpack_list(cls, *args):
        return cls(*args)


class RelayBalanceResponsePayload(BalanceResponsePayload):
    msg_id = 27


@vp_compile
class BalanceRequestPayload(VariablePayload):
    msg_id = 24
    format_list = ['I']
    names = ['circuit_id']


@vp_compile
class RelayBalanceRequestPayload(VariablePayload):
    msg_id = 25
    format_list = ['I']
    names = ['circuit_id']


@vp_compile
class HTTPRequestPayload(VariablePayload):
    msg_id = 28
    format_list = ['I', 'I', 'varlenH', 'varlenH']
    names = ['circuit_id', 'identifier', 'target', 'request']


@vp_compile
class HTTPResponsePayload(VariablePayload):
    msg_id = 29
    format_list = ['I', 'I', 'H', 'H', 'varlenH']
    names = ['circuit_id', 'identifier', 'part', 'total', 'response']
