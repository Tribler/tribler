import time
import hashlib

from collections import defaultdict


class Value(object):
    """
    Class for storing DHT values.
    """

    def __init__(self, id_, data, max_age, version):
        self.id = id_
        self.data = data
        self.last_update = time.time()
        self.max_age = max_age
        self.version = version

    @property
    def age(self):
        return time.time() - self.last_update

    @property
    def expired(self):
        return self.age > self.max_age

    def __eq__(self, other):
        return self.id == other.id


class Storage(object):
    """
    Class for storing key-value pairs in memory.
    """

    def __init__(self):
        self.items = defaultdict(list)

    def put(self, key, data, id_=None, max_age=86400, version=0):
        id_ = id_ or hashlib.sha1(data).digest()
        new_value = Value(id_, data, max_age, version)

        try:
            index = self.items[key].index(new_value)
            old_value = self.items[key][index]
            if new_value.version >= old_value.version:
                del self.items[key][index]
                self.items[key].insert(0, new_value)
                self.items[key].sort(key=lambda v: 1 if v.id == key else 0)
        except ValueError:
            self.items[key].insert(0, new_value)
            self.items[key].sort(key=lambda v: 1 if v.id == key else 0)

    def get(self, key, limit=None):
        return [value.data for value in self.items[key][:limit]]

    def items_older_than(self, min_age):
        items = []
        for key in self.items:
            items += [(key, value.data) for value in self.items[key] if value.age > min_age]
        return items

    def clean(self):
        for key in self.items:
            for index, value in reversed(list(enumerate(self.items[key]))):
                if value.expired:
                    del self.items[key][index]
                else:
                    break
