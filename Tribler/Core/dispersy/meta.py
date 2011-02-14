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
            return "<{0.meta.__class__.__name__}.{0.__class__.__name__}>".format(self)

    def __str__(self):
        return "<{0.__class__.__name__}>".format(self)

    def implement(self, *args, **kargs):
        try:
            return self.Implementation(self, *args, **kargs)
        except TypeError:
            dprint("TypeError in <{0.__class__.__name__}.{0.Implementation.__name__}>".format(self), level="error")
            dprint("self.Implementation takes: ", inspect.getargspec(self.Implementation.__init__), level="error")
            dprint("self.Implementation got: ", args, " ", kargs, level="error")
            raise
