import inspect
from dprint import dprint

class MetaObject(object):
    class Implementation(object):
        def __init__(self, meta):
            assert isinstance(meta, MetaObject)
            self._meta = meta

        @property
        def meta(self):
            return self._meta

        def __str__(self):
            return "<%s.%s>" % (self._meta.__class__.__name__, self.__class__.__name__)

    def __str__(self):
        return "<%s>" % self.__class__.__name__

    def implement(self, *args, **kargs):
        try:
            return self.Implementation(self, *args, **kargs)
        except TypeError:
            dprint("TypeError in ", self.__class__.__name__, ".", self.Implementation.__name__, level="error")
            dprint("self.Implementation takes: ", inspect.getargspec(self.Implementation.__init__), level="error")
            dprint("self.Implementation got: ", args, " ", kargs, level="error")
            raise
