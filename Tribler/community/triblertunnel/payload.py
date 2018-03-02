from Tribler.pyipv8.ipv8.attestation.trustchain.payload import HalfBlockPayload


class PayoutPayload(HalfBlockPayload):

    format_list = HalfBlockPayload.format_list + ["I", "I"]

    def __init__(self, public_key, sequence_number, link_public_key, link_sequence_number, previous_hash,
                 signature, transaction, circuit_id, base_amount):
        super(PayoutPayload, self).__init__(public_key, sequence_number, link_public_key, link_sequence_number,
                                            previous_hash, signature, transaction)
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
            block.transaction,
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
