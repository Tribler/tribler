import plyvel

class LevelDB(object):

    def __init__(self, state_dir, store_dir, create_if_missing=True):
        self._db = plyvel.DB(store_dir, create_if_missing=create_if_missing)

    def Get(self, key, verify_checksums=False, fill_cache=True):
        val = self._db.get(key, verify_checksums=verify_checksums, fill_cache=fill_cache)
        if val:
            return val
        raise KeyError('No value for key {key}'.format(key=key))

    def Put(self, key, value, sync=False):
        self._db.put(key, value, sync=sync)

    def Delete(self, key, sync=False):
        return self._db.delete(key, sync=sync)

    def RangeIter(self, key_from=None, key_to=None, include_value=True, verify_checksums=False, fill_cache=True):
        return self._db.iterator(start=key_from, stop=key_to, include_value=include_value, 
            verify_checksums=verify_checksums, fill_cache=fill_cache)

    def Write(self, write_batch, sync=False):
        write_batch._batch.write()

    def GetStats(self):
        pass # No such method in plyvel


class WriteBatch(object):

    def __init__(self, db):
        self._batch = db._db.write_batch()

    def Put(self, key, value):
        self._batch.put(key, value)

    def Delete(self, key):
        self._batch.delete(key)