from Tribler.pyipv8.ipv8.attestation.trustchain.block import TrustChainBlock, EMPTY_SIG, ValidationResult,\
    GENESIS_SEQ, GENESIS_HASH


class TriblerBandwidthBlock(TrustChainBlock):
    """
    Container for bandwidth block information
    """

    @classmethod
    def create(cls, block_type, transaction, database, public_key, link=None, link_pk=None):
        """
        Create an empty next block.
        :param block_type: the type of the block to be created
        :param transaction: the transaction to use in this block
        :param database: the database to use as information source
        :param public_key: the public key to use for this block
        :param link: optionally create the block as a linked block to this block
        :param link_pk: the public key of the counterparty in this transaction
        :return: A newly created block
        """
        latest_bw_block = database.get_latest(public_key, block_type='tribler_bandwidth')
        latest_block = database.get_latest(public_key)
        ret = cls()
        if link:
            ret.type = link.type
            ret.transaction["up"] = link.transaction["down"] if "down" in link.transaction else 0
            ret.transaction["down"] = link.transaction["up"] if "up" in link.transaction else 0
            ret.link_public_key = link.public_key
            ret.link_sequence_number = link.sequence_number
        else:
            ret.type = block_type
            ret.transaction["up"] = transaction["up"] if "up" in transaction else 0
            ret.transaction["down"] = transaction["down"] if "down" in transaction else 0
            ret.link_public_key = link_pk

        if latest_bw_block:
            ret.transaction["total_up"] = latest_bw_block.transaction["total_up"] + ret.transaction["up"]
            ret.transaction["total_down"] = latest_bw_block.transaction["total_down"] + ret.transaction["down"]
        else:
            ret.transaction["total_up"] = ret.transaction["up"]
            ret.transaction["total_down"] = ret.transaction["down"]

        if latest_block:
            ret.sequence_number = latest_block.sequence_number + 1
            ret.previous_hash = latest_block.hash

        ret.public_key = public_key
        ret.signature = EMPTY_SIG

        return ret

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

        if self.transaction["up"] < 0:
            err("Up field is negative")
        if self.transaction["down"] < 0:
            err("Down field is negative")
        if self.transaction["down"] == 0 and self.transaction["up"] == 0:
            # In this case the block doesn't modify any counters, these block are without purpose and are thus invalid.
            err("Up and down are zero")
        if self.transaction["total_up"] < 0:
            err("Total up field is negative")
        if self.transaction["total_down"] < 0:
            err("Total down field is negative")

        blk = database.get(self.public_key, self.sequence_number)
        link = database.get_linked(self)
        prev_blk = database.get_block_before(self, block_type='tribler_bandwidth')
        next_blk = database.get_block_after(self, block_type='tribler_bandwidth')

        is_genesis = self.sequence_number == GENESIS_SEQ or self.previous_hash == GENESIS_HASH
        if is_genesis:
            if self.transaction["total_up"] != self.transaction["up"]:
                err("Genesis block invalid total_up and/or up")
            if self.transaction["total_down"] != self.transaction["down"]:
                err("Genesis block invalid total_down and/or down")

        if blk:
            if blk.transaction["up"] != self.transaction["up"]:
                err("Up does not match known block")
            if blk.transaction["down"] != self.transaction["down"]:
                err("Down does not match known block")
            if blk.transaction["total_up"] != self.transaction["total_up"]:
                err("Total up does not match known block")
            if blk.transaction["total_down"] != self.transaction["total_down"]:
                err("Total down does not match known block")

        if link:
            if self.transaction["up"] != link.transaction["down"]:
                err("Up/down mismatch on linked block")
            if self.transaction["down"] != link.transaction["up"]:
                err("Down/up mismatch on linked block")

        if prev_blk:
            if prev_blk.transaction["total_up"] + self.transaction["up"] > self.transaction["total_up"]:
                err("Total up is lower than expected compared to the preceding block")
            if prev_blk.transaction["total_down"] + self.transaction["down"] > self.transaction["total_down"]:
                err("Total down is lower than expected compared to the preceding block")

        if next_blk:
            if self.transaction["total_up"] + next_blk.transaction["up"] > next_blk.transaction["total_up"]:
                err("Total up is higher than expected compared to the next block")
                # In this case we could say there is fraud too, since the counters are too high. Also anyone that
                # counter signed any such counters should be suspected since they apparently failed to validate or put
                # their signature on it regardless of validation status. But it is not immediately clear where this
                # error occurred, it might be lower on the chain than self. So it is hard to create a fraud proof here
            if self.transaction["total_down"] + next_blk.transaction["down"] > next_blk.transaction["total_down"]:
                err("Total down is higher than expected compared to the next block")
                # See previous comment

        return result[0], errors
