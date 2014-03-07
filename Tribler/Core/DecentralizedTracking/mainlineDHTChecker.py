# written by Arno Bakker, Yuan Yuan
# Modified by Raul Jimenez to integrate KTH DHT
# see LICENSE.txt for license information

import logging


class mainlineDHTChecker:
    __single = None

    def __init__(self):
        self._logger = logging.getLogger(self.__class__.__name__)
        self._logger.debug('mainlineDHTChecker: initialization')

        if mainlineDHTChecker.__single:
            raise RuntimeError("mainlineDHTChecker is Singleton")
        mainlineDHTChecker.__single = self

        self._dht = None

    def getInstance(*args, **kw):
        if mainlineDHTChecker.__single is None:
            mainlineDHTChecker(*args, **kw)
        return mainlineDHTChecker.__single
    getInstance = staticmethod(getInstance)

    def register(self, dht):
        self._dht = dht
