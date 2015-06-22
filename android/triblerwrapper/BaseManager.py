# coding: utf-8
# Written by Wendo Sabée
# A base class for all the Manager classes

class BaseManager(object):
    # Code to make this a singleton
    __single = None

    _connected = False
    _session = None

    def __init__(self, session):
        """
        Constructor for the BaseManager that checks singleton status.
        :param session: The Tribler session that this BaseManager should apply to.
        :return:
        """
        if BaseManager.__single:
            raise RuntimeError("%s is singleton" % self.__class__)
        self._connected = False

        self._session = session

    @classmethod
    def getInstance(cls, *args, **kw):
        if cls.__single is None:
            cls.__single = cls(*args, **kw)
        return cls.__single #return BaseManager.__single

    @classmethod
    def delInstance(cls, *args, **kw):
        cls.__single = None
