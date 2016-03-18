from hashlib import sha256
from struct import pack_into, unpack_from, calcsize

from Tribler.dispersy.crypto import ECCrypto

# TODO: derive these at run time?
HASH_LENGTH = 32
SIG_LENGTH = 64
PK_LENGTH = 74

GENESIS_ID = '0'*HASH_LENGTH    # ID of the first block of the chain.
EMPTY_SIG = '0'*SIG_LENGTH
EMPTY_PK = '0'*PK_LENGTH

block_pack_format = "! I I Q Q {0}s i {0}s i {1}s {2}s".format(PK_LENGTH, HASH_LENGTH, SIG_LENGTH)
block_pack_size = calcsize(block_pack_format)


class MultiChainBlock(object):
    """
    Container for MultiChain block information
    """

    def __init__(self, data=None):
        if data is None:
            # data
            self.up = self.down = 0
            self.total_up = self.total_down = 0
            # identity
            self.public_key = EMPTY_PK
            self.sequence_number = 1
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

    @property
    def hash(self):
        return sha256(self.pack()).digest()

    def validate(self, database):
        """
        Validates this block against what is known in the database
        :param database: the database to check against
        :return: complex stuff
        """
        # TODO: validate
        # TODO: validate signature to public key
        pass

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
            ret.sequence_number = 1
            ret.previous_hash = GENESIS_ID
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
