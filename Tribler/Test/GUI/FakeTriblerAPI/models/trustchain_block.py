from random import randint, choice, random

import datetime


class TrustchainBlock:

    def __init__(self, my_id=None, timestamp=0, last_block=None):
        self.public_key = my_id
        self.sequence_number = 1 if last_block is None else last_block.sequence_number + 1
        self.up = randint(1024, 30 * 1024) * 1024
        self.down = randint(1024, 20 * 1024) * 1024
        self.total_up = (last_block.total_up if last_block else 0) + self.up
        self.total_down = (last_block.total_down if last_block else 0) + self.down
        self.transaction = {"up": self.up, "down": self.down, "total_up": self.total_up, "total_down": self.total_down}
        self.link_public_key = 'b' * 20
        self.link_sequence_number = 0 if random() < 0.5 else randint(1, 1000)
        self.previous_hash = 'c' * 20
        self.signature = 'd' * 20
        self.insert_time = datetime.datetime.fromtimestamp(int(timestamp)).strftime('%Y-%m-%d %H:%M:%S')
        self.type = 'tribler_bandwidth'

    def to_dictionary(self):
        return {
            "transaction": self.transaction,
            "up": self.up,
            "down": self.down,
            "total_up": self.total_up,
            "total_down": self.total_down,
            "public_key": self.public_key.encode("hex"),
            "sequence_number": self.sequence_number,
            "link_public_key": self.link_public_key.encode("hex"),
            "link_sequence_number": self.link_sequence_number,
            "previous_hash": self.previous_hash.encode("hex"),
            "signature": self.signature.encode("hex"),
            "insert_time": self.insert_time,
            "hash": ('e' * 20).encode("hex"),
            "type": self.type
        }
