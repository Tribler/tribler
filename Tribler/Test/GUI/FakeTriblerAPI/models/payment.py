from __future__ import absolute_import

import random

from six.moves import xrange


class Payment(object):

    def __init__(self, transaction):
        self.trader_id = transaction.trader_id
        self.transaction_number = transaction.transaction_number
        self.transferred_amount = transaction.asset1_amount
        self.transferred_type = transaction.asset1_type
        self.address_from = 'a' * 10
        self.address_to = 'b' * 10
        self.timestamp = transaction.timestamp + 10
        self.payment_id = ''.join(random.choice('0123456789abcdef') for _ in xrange(16))
        self.success = random.random() > 0.5

    def get_json(self):
        return {
            "trader_id": self.trader_id,
            "transaction_number": self.transaction_number,
            "transferred": {
                "amount": self.transferred_amount,
                "type": self.transferred_type
            },
            "payment_id": self.payment_id,
            "address_from": self.address_from,
            "address_to": self.address_to,
            "timestamp": self.timestamp,
            "success": self.success
        }
