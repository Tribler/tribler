import codecs
import logging
import os

import Tribler.Core.Utilities.json_util as json


class SimpleCache(object):
    """
    This is a cache for recording the keys that we have seen before.
    """
    def __init__(self, file_path):
        self._logger = logging.getLogger(self.__class__.__name__)
        self._file_path = file_path

        self._cache_list = list()
        self._initial_cache_size = 0

    def add(self, key):
        if not self.has(key):
            self._cache_list.append(key)

    def has(self, key):
        return key in self._cache_list

    def load(self):
        if os.path.exists(self._file_path):
            try:
                with codecs.open(self._file_path, 'rb', encoding='utf-8') as f:
                    self._cache_list = json.load(f)
            except Exception as e:
                self._logger.error(u"Failed to load cache file %s: %s", self._file_path, repr(e))
        else:
            self._cache_list = list()
        self._initial_cache_size = len(self._cache_list)

    def save(self):
        if self._initial_cache_size == len(self._cache_list):
            return
        try:
            with codecs.open(self._file_path, 'wb', encoding='utf-8') as f:
                json.dump(self._cache_list, f)
                self._initial_cache_size = len(self._cache_list)
        except Exception as e:
            self._logger.error(u"Failed to save cache file %s: %s", self._file_path, repr(e))
            return
