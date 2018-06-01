import time

from collections import defaultdict


class Storage(object):
    """
    Class for storing key-value pairs in memory.
    """

    def __init__(self):
        self.data = defaultdict(list)

    def put(self, key, value, max_age):
        for i, v in enumerate(self.data[key]):
            if v[-1] == value:
                del self.data[key][i]

        self.data[key].append((time.time(), max_age, value))

    def get(self, key):
        return [value for _, _, value in self.data[key]]

    def items_older_than(self, min_age):
        now = time.time()

        items = []
        for key in self.data:
            items += [(key, value) for ts, _, value in self.data[key] if now - ts > min_age]
        return items

    def clean(self):
        now = time.time()
        for key in self.data:
            for index, (ts, max_age, _) in enumerate(self.data[key]):
                if now - ts > max_age:
                    del self.data[key][index]
                else:
                    break
