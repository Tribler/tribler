import random

import time


class Order:

    def __init__(self, asset1_type, asset2_type):
        self.trader_id = ''.join(random.choice('0123456789abcdef') for _ in xrange(16))
        now = int(time.time())
        self.timestamp = random.randint(now - 3600, now)
        self.asset1_amount = random.randint(1, 100)
        self.asset1_type = asset1_type
        self.asset2_amount = random.randint(1, 100)
        self.asset2_type = asset2_type
        self.traded_quantity = random.randint(0, self.asset1_amount)
        self.reserved_quantity = random.randint(0, self.asset1_amount - self.traded_quantity)
        self.is_ask = random.random() < 0.5
        self.order_number = random.randint(1, 50)
        self.status = random.choice(['open', 'completed', 'expired', 'cancelled'])

    def get_json(self):
        return {
            "trader_id": self.trader_id,
            "order_number": self.order_number,
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
            "reserved_quantity": self.reserved_quantity,
            "traded": self.traded_quantity,
            "timeout": 3600,
            "timestamp": self.timestamp,
            "completed_timestamp": None,
            "is_ask": self.is_ask,
            "cancelled": self.status != 'cancelled',
            "status": self.status
        }
