class DeclinedTradeReason(object):
    ORDER_COMPLETED = 0
    ORDER_EXPIRED = 1
    ORDER_RESERVED = 2
    ORDER_INVALID = 3
    UNACCEPTABLE_PRICE = 4


class DeclineMatchReason(object):
    ORDER_COMPLETED = 0
    OTHER_ORDER_COMPLETED = 1
    OTHER = 2
