from Tribler.community.trustchain.block import TrustChainBlock, ValidationResult, GENESIS_SEQ, GENESIS_HASH, EMPTY_SIG


class TriblerChainBlock(TrustChainBlock):
    """
    Container for TriblerChain block information
    """

    def __init__(self, data=None):
        super(TriblerChainBlock, self).__init__(data)
        if len(self.transaction) != 4:
            self.transaction = [0, 0, 0, 0]
        for i in range(0, 4):
            if not isinstance(self.transaction[i], int):
                self.transaction[i] = int(self.transaction[i])

    @classmethod
    def create(cls, transaction, database, public_key, link=None, link_pk=None):
        """
        Create an empty next block.
        :param database: the database to use as information source
        :param transaction: the transaction to use in this block
        :param public_key: the public key to use for this block
        :param link: optionally create the block as a linked block to this block
        :param link_pk: the public key of the counterparty in this transaction
        :return: A newly created block
        """
        blk = database.get_latest(public_key)
        ret = cls()
        if link:
            ret.up = link.down
            ret.down = link.up
            ret.link_public_key = link.public_key
            ret.link_sequence_number = link.sequence_number
        else:
            ret.up = transaction[0]
            ret.down = transaction[1]
            ret.link_public_key = link_pk

        if blk:
            ret.total_up = blk.total_up + ret.up
            ret.total_down = blk.total_down + ret.down
            ret.sequence_number = blk.sequence_number + 1
            ret.previous_hash = blk.hash
        else:
            ret.total_up = ret.up
            ret.total_down = ret.down

        ret.public_key = public_key
        ret.signature = EMPTY_SIG

        return ret

    @property
    def up(self):
        return self.transaction[0]

    @up.setter
    def up(self, value):
        assert isinstance(value, int), "Must assign int!"
        self.transaction[0] = value

    @property
    def down(self):
        return self.transaction[1]

    @down.setter
    def down(self, value):
        assert isinstance(value, int), "Must assign int!"
        self.transaction[1] = value

    @property
    def total_up(self):
        return self.transaction[2]

    @total_up.setter
    def total_up(self, value):
        assert isinstance(value, int), "Must assign int!"
        self.transaction[2] = value

    @property
    def total_down(self):
        return self.transaction[3]

    @total_down.setter
    def total_down(self, value):
        assert isinstance(value, int), "Must assign int!"
        self.transaction[3] = value

    def validate_transaction(self, database):
        """
        Validates this transaction
        :param transaction the transaction to validate
        :param database: the database to check against
        :return: A tuple consisting of a ValidationResult and a list of user string errors
        """
        result = [ValidationResult.valid]
        errors = []

        def err(reason):
            result[0] = ValidationResult.invalid
            errors.append(reason)

        if self.up < 0:
            err("Up field is negative")
        if self.down < 0:
            err("Down field is negative")
        if self.down == 0 and self.up == 0:
            # In this case the block doesn't modify any counters, these block are without purpose and are thus invalid.
            err("Up and down are zero")
        if self.total_up < 0:
            err("Total up field is negative")
        if self.total_down < 0:
            err("Total down field is negative")

        blk = database.get(self.public_key, self.sequence_number)
        link = database.get_linked(self)
        prev_blk = database.get_block_before(self)
        next_blk = database.get_block_after(self)

        is_genesis = self.sequence_number == GENESIS_SEQ or self.previous_hash == GENESIS_HASH
        if is_genesis:
            if self.total_up != self.up:
                err("Genesis block invalid total_up and/or up")
            if self.total_down != self.down:
                err("Genesis block invalid total_down and/or down")

        if blk:
            if blk.up != self.up:
                err("Up does not match known block")
            if blk.down != self.down:
                err("Down does not match known block")
            if blk.total_up != self.total_up:
                err("Total up does not match known block")
            if blk.total_down != self.total_down:
                err("Total down does not match known block")

        if link:
            if self.up != link.down:
                err("Up/down mismatch on linked block")
            if self.down != link.up:
                err("Down/up mismatch on linked block")

        if prev_blk:
            if prev_blk.total_up + self.up > self.total_up:
                err("Total up is lower than expected compared to the preceding block")
            if prev_blk.total_down + self.down > self.total_down:
                err("Total down is lower than expected compared to the preceding block")

        if next_blk:
            if self.total_up + next_blk.up > next_blk.total_up:
                err("Total up is higher than expected compared to the next block")
                # In this case we could say there is fraud too, since the counters are too high. Also anyone that
                # counter signed any such counters should be suspected since they apparently failed to validate or put
                # their signature on it regardless of validation status. But it is not immediately clear where this
                # error occurred, it might be lower on the chain than self. So it is hard to create a fraud proof here
            if self.total_down + next_blk.down > next_blk.total_down:
                err("Total down is higher than expected compared to the next block")
                # See previous comment

        return result[0], errors
