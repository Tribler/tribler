from threading import RLock


class Singleton(object):

    __singleton = None

    def __init__(self):
        if Singleton.__singleton:
            raise RuntimeError(u"Recreating singleton %s" % self.__class__.__name__)
        super(Singleton, self).__init__()

    @classmethod
    def getInstance(cls, *args, **kwargs):
        if cls.__singleton is None:
            if cls.__singleton is None:
                cls.__singleton = cls(*args, **kwargs)
        return cls.__singleton

    @classmethod
    def delInstance(cls):
        cls.__singleton = None

    @classmethod
    def hasInstance(cls):
        return cls.__singleton != None


class ThreadSafeSingleton(object):

    __singleton = None
    __singleton_lock = RLock()

    def __init__(self):
        if ThreadSafeSingleton.__singleton:
            raise RuntimeError(u"Recreating singleton %s" % self.__class__.__name__)
        super(ThreadSafeSingleton, self).__init__()

    @classmethod
    def getInstance(cls, *args, **kwargs):
        with cls.__singleton_lock:
            if cls.__singleton is None:
                if cls.__singleton is None:
                    cls.__singleton = cls(*args, **kwargs)
            return cls.__singleton

    @classmethod
    def delInstance(cls):
        with cls.__singleton_lock:
            cls.__singleton = None

    @classmethod
    def hasInstance(cls):
        with cls.__singleton_lock:
            return cls.__singleton != None
