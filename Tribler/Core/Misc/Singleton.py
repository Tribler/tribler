from threading import RLock

from Tribler.Core.Misc.GenericModule import GenericModule

class Singleton(GenericModule):

    """
    A non-thread-safe singleton meta class.
    """

    __singleton = None

    def __init__(self):
        if Singleton.__singleton:
            raise RuntimeError(u"Recreating singleton %s" % self.__class__.__name__)
        super(Singleton, self).__init__()

    @classmethod
    def getInstance(cls, *args, **kwargs):
        """Gets the singleton instance.
        """
        if cls.__singleton is None:
            if cls.__singleton is None:
                cls.__singleton = cls(*args, **kwargs)
        return cls.__singleton

    @classmethod
    def delInstance(cls):
        """Deletes the singleton instance.
        """
        if cls.__singleton:
            cls.__singleton.finalize()
            cls.__singleton = None

    @classmethod
    def hasInstance(cls):
        """Checks if the singleton instance exists.
        """
        return cls.__singleton != None


class ThreadSafeSingleton(GenericModule):

    """
    A thread-safe singleton meta class.
    """

    __singleton = None
    __singleton_lock = RLock()

    def __init__(self):
        if ThreadSafeSingleton.__singleton:
            raise RuntimeError(u"Recreating singleton %s" % self.__class__.__name__)
        super(ThreadSafeSingleton, self).__init__()

    @classmethod
    def getInstance(cls, *args, **kwargs):
        """Gets the singleton instance.
        """
        with cls.__singleton_lock:
            if cls.__singleton is None:
                if cls.__singleton is None:
                    cls.__singleton = cls(*args, **kwargs)
            return cls.__singleton

    @classmethod
    def delInstance(cls):
        """Deletes the singleton instance.
        """
        with cls.__singleton_lock:
            if cls.__singleton:
                cls.__singleton.finalize()
                cls.__singleton = None

    @classmethod
    def hasInstance(cls):
        """Checks if the singleton instance exists.
        """
        with cls.__singleton_lock:
            return cls.__singleton != None
