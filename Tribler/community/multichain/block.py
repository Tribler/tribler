from hashlib import sha256
from struct import pack_into, unpack_from, calcsize

from Tribler.dispersy.crypto import ECCrypto

# TODO: derive these at run time?
HASH_LENGTH = 32
SIG_LENGTH = 64
PK_LENGTH = 74

GENESIS_ID = '0'*HASH_LENGTH    # ID of the first block of the chain.
GENESIS_SEQ = 1
EMPTY_SIG = '0'*SIG_LENGTH
EMPTY_PK = '0'*PK_LENGTH

block_pack_format = "! Q Q Q Q {0}s I {0}s I {1}s {2}s".format(PK_LENGTH, HASH_LENGTH, SIG_LENGTH)
block_pack_size = calcsize(block_pack_format)

VALID="valid"
PARTIAL="partial"
PARTIAL_NEXT=PARTIAL+"-next"
PARTIAL_PREV=PARTIAL+"-prev"
NO_INFO="no-info"
INVALID="invalid"


class MultiChainBlock(object):
    """
    Container for MultiChain block information
    """

    def __init__(self, data=None):
        super(MultiChainBlock, self).__init__()
        if data is None:
            # data
            self.up = self.down = 0
            self.total_up = self.total_down = 0
            # identity
            self.public_key = EMPTY_PK
            self.sequence_number = GENESIS_SEQ
            # linked identity
            self.link_public_key = EMPTY_PK
            self.link_sequence_number = 0
            # validation
            self.previous_hash = GENESIS_ID
            self.signature = EMPTY_SIG
            # debug stuff
            self.insert_time = None
        else:
            (self.up, self.down, self.total_up, self.total_down, self.public_key, self.sequence_number,
             self.link_public_key, self.link_sequence_number, self.previous_hash, self.signature,
             self.insert_time) = (data[0], data[1], data[2], data[3], data[4], data[5], data[6], data[7], data[8],
                                  data[9], data[10])
            if isinstance(self.public_key, buffer):
                self.public_key = str(self.public_key)
            if isinstance(self.link_public_key, buffer):
                self.link_public_key = str(self.link_public_key)
            if isinstance(self.previous_hash, buffer):
                self.previous_hash = str(self.previous_hash)
            if isinstance(self.signature, buffer):
                self.signature = str(self.signature)

    @property
    def hash(self):
        return sha256(self.pack()).digest()

    def validate(self, database):
        """
        Validates this block against what is known in the database
        :param database: the database to check against
        :return: VALID if the block does not violate any rules,
                 PARTIAL_NEXT if the block does not violate any rules, but there is a gap or no block in the future
                 PARTIAL_PREV if the block does not violate any rules, but there is a gap or no block in the past
                 PARTIAL if the block does not violate any rules, but there are gaps or no blocks on either side
                 NO_INFO if there is not enough information known about the block to validate
                 INVALID if the block violates any of the rules
        """

        result = [VALID]
        errors = []
        crypto = ECCrypto()

        def err(reason):
            result[0] = INVALID
            errors.append(reason)

        # Step 1: get all related blocks from the database, assume that the database speaks the truth and that all
        # retrieved blocks are not invalid themselves. Thus the database should reject adding blocks that have "invalid"
        # as validation result.
        blk = database.get(self.public_key, self.sequence_number)
        link = database.get_linked(self)
        prev_blk = (database.get_blocks_until(self.public_key, self.sequence_number - 1, limit=1) or [None])[0]
        next_blk = (database.get_blocks_since(self.public_key, self.sequence_number + 1, limit=1) or [None])[0]

        # Step 2: determine the maximum validation level
        if not prev_blk and not next_blk:
            if self.sequence_number != GENESIS_SEQ and self.previous_hash != GENESIS_ID:
                # No blocks found, there is no info to base on
                err("No blocks are known for this member before or after the queried sequence number")
                result[0] = NO_INFO
            else:
                # If it is a starting block, we can at least conclude that the start is right if the totals add up
                result[0] = PARTIAL_NEXT
        elif not prev_blk and next_blk:
            # The previous block does not exist in the database, at best our result can now be partial w.r.t. prev
            if self.sequence_number != GENESIS_SEQ and self.previous_hash != GENESIS_ID:
                # We are not checking the first block after genesis, so we are really missing the previous block
                result[0] = PARTIAL_PREV
                if next_blk.sequence_number != self.sequence_number + 1:
                    # If both sides are unknown or non-contiguous return a full partial result.
                    result[0] = PARTIAL
        elif prev_blk and not next_blk:
            # The next block does not exist in the database, at best our result can now be partial w.r.t. next
            result[0] = PARTIAL_NEXT
            if prev_blk.sequence_number != self.sequence_number - 1:
                # If both sides are unknown or non-contiguous return a full partial result.
                result[0] = PARTIAL
        else:
            # both sides have known blocks, see if there are gaps
            if (prev_blk.sequence_number != self.sequence_number - 1) and \
                    (next_blk.sequence_number != self.sequence_number + 1):
                result[0] = PARTIAL
            elif prev_blk.sequence_number != self.sequence_number - 1:
                result[0] = PARTIAL_PREV
            elif next_blk.sequence_number != self.sequence_number + 1:
                result[0] = PARTIAL_NEXT

        # Step 3: validate that the block is sane
        if self.up < 0:
            err("Up field is negative")
        if self.down < 0:
            err("Down field is negative")
        if self.total_up < 0:
            err("Total up field is negative")
        if self.total_down < 0:
            err("Total down field is negative")
        if self.sequence_number < GENESIS_SEQ:
            err("Sequence number is prior to genesis")
        if self.link_sequence_number < 0:
            err("Link sequence number not empty and is prior to genesis")
        if not crypto.is_valid_public_bin(self.public_key):
            err("Public key is not valid")
        else:
            try:
                pck = self.pack(signature=False)
            except:
                pck = None
            if pck is None or not crypto.is_valid_signature(
                    crypto.key_from_public_bin(self.public_key), pck, self.signature):
                err("Invalid signature")
        if not crypto.is_valid_public_bin(self.link_public_key):
            err("Linked public key is not valid")
        if self.public_key == self.link_public_key:
            err("Self signed block")
        if self.sequence_number == GENESIS_SEQ or self.previous_hash == GENESIS_ID:
            if self.sequence_number == GENESIS_SEQ and self.previous_hash != GENESIS_ID:
                err("Sequence number implies previous hash should be Genesis ID")
            if self.sequence_number != GENESIS_SEQ and self.previous_hash == GENESIS_ID:
                err("Sequence number implies previous hash should not be Genesis ID")
            if self.total_up != self.up:
                err("Genesis block invalid total_up and/or up")
            if self.total_down != self.down:
                err("Genesis block invalid total_down and/or down")

        # Step 3: does the database already know about this block? If so, is it equal?
        if blk:
            # TODO: if the block is valid upto this point (specifically the signature is valid), and an error is
            # detected here, it is in fact fraud, since a PK/seq pair is double signed.
            if blk.up != self.up:
                err("Up does not match known block")
            if blk.down != self.down:
                err("Down does not match known block")
            if blk.total_up != self.total_up:
                err("Total up does not match known block")
            if blk.total_down != self.total_down:
                err("Total down does not match known block")
            if blk.link_public_key != self.link_public_key:
                err("Link public key does not match known block")
            if blk.link_sequence_number != self.link_sequence_number:
                err("Link sequence number does not match known block")
            if blk.previous_hash != self.previous_hash:
                err("Previous hash does not match known block")
            if blk.signature != self.signature:
                err("Signature does not match known block")

        # Step 4: does the database have the linked block? If so do the values match up?
        if link:
            if self.up != link.down:
                err("Up/down mismatch on linked block")
            if self.down != link.up:
                err("Down/up mismatch on linked block")

        # Step 5: does the database have adjacent blocks?
        if prev_blk:
            if prev_blk.total_up + self.up > self.total_up:
                err("Total up is lower than expected compared to the preceding block")
            if prev_blk.total_down + self.down > self.total_down:
                err("Total down is lower than expected compared to the preceding block")
            if prev_blk.sequence_number == self.sequence_number - 1 and prev_blk.hash != self.previous_hash:
                err("Previous hash is not equal to the hash id of the previous block")

        if next_blk:
            if self.total_up + next_blk.up > next_blk.total_up:
                err("Total up is higher than expected compared to the next block")
            if self.total_down + next_blk.down > next_blk.total_down:
                err("Total down is higher than expected compared to the next block")
            if next_blk.sequence_number == self.sequence_number + 1 and next_blk.previous_hash != self.hash:
                err("Next hash is not equal to the hash id of the block")

        # TODO: Detect fraud? But should it go here?
        # Fraud detection might be easier if you inspect the database for all public key's in one go. (Or rather it
        # might lead to a lot of double work if you do the fraud detection for each PK individually)
        # Also if this method returns "invalid" for fraud cases, then those blocks cannot be kept in the database for
        # future reference or as fraud proofs.

        return result[0], errors

    def sign(self, key):
        """
        Signs this block with the given key
        :param key: the key to sign this block with
        """
        crypto = ECCrypto()
        self.signature = crypto.create_signature(key, self.pack(signature=False))

    @classmethod
    def create(cls, database, public_key, link=None):
        """
        Create next block. Initializes a new block based on the latest information in the database
        and optional linked block
        :param database: the database to use as information source
        :param public_key: the public key to use for this block
        :param link: optionally create the block as a linked block to this block
        :return: A newly created block
        """
        blk = database.get_latest(public_key)
        ret = cls()
        if link:
            ret.up = link.down
            ret.down = link.up
            ret.link_public_key = link.public_key
            ret.link_sequence_number = link.sequence_number
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

    def pack(self, data=None, offset=0, signature=True):
        """
        Encode this block for transport
        :param data: optionally specify the buffer this block should be packed into
        :param offset: optionally specifies the offset at which the packing should begin
        :param signature: False to pack EMPTY_SIG in the signature location, true to pack the signature field
        :return: the buffer the data was packed into
        """
        buff = data if data else bytearray(block_pack_size)
        pack_into(block_pack_format, buff, offset, self.up, self.down, self.total_up, self.total_down, self.public_key,
                  self.sequence_number, self.link_public_key, self.link_sequence_number, self.previous_hash,
                  self.signature if signature else EMPTY_SIG)
        return str(buff)

    @classmethod
    def unpack(cls, data, offset=0):
        """
        Unpacks a block from a buffer
        :param data: The buffer to unpack from
        :param offset: Optionally, the offset at which to start unpacking
        :return: The MultiChainBlock that was unpacked from the buffer
        """
        ret = MultiChainBlock()
        (ret.up, ret.down, ret.total_up, ret.total_down, ret.public_key, ret.sequence_number, ret.link_public_key,
         ret.link_sequence_number, ret.previous_hash, ret.signature) = unpack_from(block_pack_format, data, offset)
        return ret

    def pack_db_insert(self):
        """
        Prepare a tuple to use for inserting into the database
        :return: A database insertable tuple
        """
        return (self.up, self.down, self.total_up, self.total_down, buffer(self.public_key), self.sequence_number,
                buffer(self.link_public_key), self.link_sequence_number, buffer(self.previous_hash),
                buffer(self.signature), buffer(self.hash))
