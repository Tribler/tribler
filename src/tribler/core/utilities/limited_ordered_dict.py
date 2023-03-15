from collections import OrderedDict


class LimitedOrderedDict(OrderedDict):
    """ This class is an implementation of OrderedDict with size limit.

    If the size of the dict exceeds the limit, the oldest entries will be deleted.
    """

    def __init__(self, *args, limit: int = 200, **kwargs):
        self.limit = limit
        super().__init__(*args, **kwargs)

    def __setitem__(self, key, value):
        super().__setitem__(key, value)
        self._adjust_size()

    def _adjust_size(self):
        while len(self) > self.limit:
            self.popitem(last=False)
