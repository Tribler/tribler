# coding: utf-8
# Written by Wendo Sabée
# A base class for all the Manager classes

class BaseManager(object):
    # Code to make this a singleton
    __single = None

    _connected = False
    _session = None

    def __init__(self, session, xmlrpc=None):
        """
        Constructor for the BaseManager that checks singleton status.
        :param session: The Tribler session that this BaseManager should apply to.
        :param xmlrpc: The XML-RPC Manager that the BaseManager should apply to. If specified, the BaseManager
        registers its public functions with the XMLRpcManager.
        :return:
        """
        if BaseManager.__single:
            raise RuntimeError("%s is singleton" % self.__class__)
        self._connected = False

        self._session = session

        self._connect()

        if xmlrpc:
            self._xmlrpc_register(xmlrpc)

    @classmethod
    def getInstance(cls, *args, **kw):
        if cls.__single is None:
            cls.__single = cls(*args, **kw)
        return cls.__single #return BaseManager.__single

    @classmethod
    def delInstance(cls, *args, **kw):
        cls.__single = None

    def _connect(self):
        """
        A function that gets called right before the _xmlrpc_register() function.
        :return:
        """
        if not self._connected:
            pass
        else:
            raise RuntimeError('%s already connected' % self.__class__)

        self._connected = True

    def _xmlrpc_register(self, xmlrpc):
        """
        Classes should implement this function if they wish to expose functions via the XMLRpcManager.
        :param xmlrpc: The XML-RPC Manager that the BaseManager should apply to. If specified, the BaseManager
        registers its public functions with the XMLRpcManager.
        :return: Nothing.
        """
        pass