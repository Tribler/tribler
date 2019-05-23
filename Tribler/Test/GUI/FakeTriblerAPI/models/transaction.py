import random

import time

from six.moves import xrange

from Tribler.Test.GUI.FakeTriblerAPI.models.payment import Payment


class Transaction(object):

    def __init__(self, price_type, quantity_type):
        self.trader_id = ''.join(random.choice('0123456789abcdef') for _ in xrange(16))
        self.partner_trader_id = ''.join(random.choice('0123456789abcdef') for _ in xrange(16))
        self.order_number = random.randint(1, 50)
        self.partner_order_number = random.randint(1, 50)
        self.transaction_number = random.randint(1, 50)
        self.asset1_amount = random.randint(1, 100)
        self.asset1_type = price_type
        self.transferred_asset1 = random.randint(0, self.asset1_amount)
        self.asset2_amount = random.randint(1, 100)
        self.asset2_type = quantity_type
        self.transferred_asset2 = random.randint(0, self.asset2_amount)
        now = int(time.time())
        self.timestamp = random.randint(now - 3600, now)
        self.payment_complete = random.random() > 0.5
        self.status = random.choice(['pending', 'completed', 'error'])
        self.payments = [Payment(self)]

    def get_json(self):
        return {
            "trader_id": self.trader_id,
            "order_number": self.order_number,
            "partner_trader_id": self.partner_trader_id,
            "partner_order_number": self.partner_order_number,
            "transaction_number": self.transaction_number,
            "assets": {
                "first": {
                    "amount": self.asset1_amount,
                    "type": self.asset1_type
                },
                "second": {
                    "amount": self.asset2_amount,
                    "type": self.asset2_type
                }
            },
            "transferred": {
                "first": {
                    "amount": self.transferred_asset1,
                    "type": self.asset1_type
                },
                "second": {
                    "amount": self.transferred_asset1,
                    "type": self.asset2_type
                }
            },
            "timestamp": self.timestamp,
            "payment_complete": self.payment_complete,
            "status": self.status
        }
