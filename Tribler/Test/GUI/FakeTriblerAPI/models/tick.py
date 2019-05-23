import random

import time


class Tick(object):

    def __init__(self, asset1_type, asset2_type, is_ask=True):
        self.is_ask = is_ask
        self.trader_id = ''.join(random.choice('0123456789abcdef') for n in xrange(16))
        self.timeout = 3600
        self.asset1_amount = random.randint(1, 100)
        self.asset1_type = asset1_type
        self.asset2_amount = random.randint(1, 100)
        self.asset2_type = asset2_type
        self.traded = random.randint(0, self.asset1_amount)

        now = int(time.time())
        self.timestamp = random.randint(now - 3600, now)
        self.order_number = random.randint(1, 50)
        self.message_id = ''.join(random.choice('0123456789abcdef') for n in xrange(16))

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
            "timeout": self.timeout,
            "timestamp": self.timestamp,
            "traded": self.traded,
            "block_hash": '0' * 40
        }
