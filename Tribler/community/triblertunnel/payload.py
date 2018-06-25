from Tribler.pyipv8.ipv8.attestation.trustchain.payload import HalfBlockPayload
from Tribler.pyipv8.ipv8.deprecated.payload import Payload


class PayoutPayload(HalfBlockPayload):

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
            block.transaction,
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

    format_list = ["I"] + HalfBlockPayload.format_list

    def __init__(self, circuit_id, public_key, sequence_number, link_public_key, link_sequence_number, previous_hash,
                 signature, block_type, transaction, timestamp):
        super(BalanceResponsePayload, self).__init__(public_key, sequence_number, link_public_key,
                                                     link_sequence_number, previous_hash, signature, block_type,
                                                     transaction, timestamp)
        self.circuit_id = circuit_id

    @classmethod
    def from_half_block(cls, block, circuit_id):
        return BalanceResponsePayload(
            circuit_id,
            block.public_key,
            block.sequence_number,
            block.link_public_key,
            block.link_sequence_number,
            block.previous_hash,
            block.signature,
            block.type,
            block.transaction,
            block.timestamp
        )

    def to_pack_list(self):
        data = super(BalanceResponsePayload, self).to_pack_list()
        data.insert(0, ('I', self.circuit_id))
        return data

    @classmethod
    def from_unpack_list(cls, *args):
        return BalanceResponsePayload(*args)


class BalanceRequestPayload(Payload):

    format_list = ['I']

    def __init__(self, circuit_id):
        super(BalanceRequestPayload, self).__init__()
        self._circuit_id = circuit_id

    def to_pack_list(self):
        data = [('I', self.circuit_id)]

        return data

    @classmethod
    def from_unpack_list(cls, circuit_id):
        return BalanceRequestPayload(circuit_id)

    @property
    def circuit_id(self):
        return self._circuit_id
