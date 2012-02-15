# Python 2.5 features
from __future__ import with_statement

"""
Helper class to easily and cleanly use singleton objects
"""

from gc import get_referrers
from random import sample
from threading import RLock

class Singleton(object):
    """
    Usage:

    class Foo(Singleton):
        def __init__(self, bar):
            self.bar = bar

    # create singleton instance and set bar = 123
    foo = Foo.get_instance(123)
    assert foo.bar == 123

    # retrieve existing singleton instance, Foo.__init__ is NOT called again
    foo = Foo.get_instance()
    assert foo.bar == 123

    # retrieve existing singleton instance, bar is NOT set to 456
    foo = Foo.get_instance(456)
    assert foo.bar == 123
    """

    _singleton_lock = RLock()

    @classmethod
    def has_instance(cls, singleton_placeholder=None):
        """
        Returns the existing singleton instance or None
        """
        if singleton_placeholder is None:
            singleton_placeholder = cls

        with singleton_placeholder._singleton_lock:
            if hasattr(singleton_placeholder, "_singleton_instance"):
                return getattr(singleton_placeholder, "_singleton_instance")

    @classmethod
    def get_instance(cls, *args, **kargs):
        """
        Returns the existing singleton instance or create one
        """
        if "singleton_placeholder" in kargs:
            singleton_placeholder = kargs.pop("singleton_placeholder")
        else:
            singleton_placeholder = cls

        with singleton_placeholder._singleton_lock:
            if not hasattr(singleton_placeholder, "_singleton_instance"):
                setattr(singleton_placeholder, "_singleton_instance", cls(*args, **kargs))
            return getattr(singleton_placeholder, "_singleton_instance")

    @classmethod
    def del_instance(cls, singleton_placeholder=None):
        """
        Removes the existing singleton instance
        """
        if singleton_placeholder is None:
            singleton_placeholder = cls

        with singleton_placeholder._singleton_lock:
            if hasattr(singleton_placeholder, "_singleton_instance"):
                delattr(singleton_placeholder, "_singleton_instance")

    @classmethod
    def referenced_instance(cls, singleton_placeholder=None):
        """
        Returns True if this singleton instance is referenced.

        Warning: this method uses the GC.get_referrers to determine the number of references.  This
        method is very expensive to use!
        """
        if singleton_placeholder is None:
            singleton_placeholder = cls

        with singleton_placeholder._singleton_lock:
            if hasattr(singleton_placeholder, "_singleton_instance"):
                return len(get_referrers(getattr(cls, "_singleton_instance"))) > 1
        return False

class Parameterized1Singleton(object):
    """
    The required first parameter is used to uniquely identify a
    singleton instance.  Only one instance per first parameter will be
    created.

    class Bar(Parameterized1Singleton):
        def __init(self, name):
            self.name = name

    a1 = Bar.get_instance('a', 'a')
    a2 = Bar.get_instance('a', *whatever)
    b1 = Bar.get_instance('b', 'b')

    assert a1 == a2
    assert a1 != b1
    assert a2 != b2

    """

    _singleton_lock = RLock()

    @classmethod
    def has_instance(cls, arg):
        """
        Returns the existing singleton instance or None
        """
        assert hasattr(arg, "__hash__")
        with cls._singleton_lock:
            if hasattr(cls, "_singleton_instances") and arg in getattr(cls, "_singleton_instances"):
                return getattr(cls, "_singleton_instances")[arg]

    @classmethod
    def get_instance(cls, *args, **kargs):
        """
        Returns the existing singleton instance or create one
        """
        assert len(args) > 0
        assert hasattr(args[0], "__hash__")
        with cls._singleton_lock:
            if not hasattr(cls, "_singleton_instances"):
                setattr(cls, "_singleton_instances", {})
            if not args[0] in getattr(cls, "_singleton_instances"):
                getattr(cls, "_singleton_instances")[args[0]] = cls(*args, **kargs)
            return getattr(cls, "_singleton_instances")[args[0]]

    @classmethod
    def del_instance(cls, arg):
        """
        Removes the existing singleton instance
        """
        assert hasattr(arg, "__hash__")
        with cls._singleton_lock:
            if hasattr(cls, "_singleton_instances") and arg in getattr(cls, "_singleton_instances"):
                del getattr(cls, "_singleton_instances")[arg]
                if not getattr(cls, "_singleton_instances"):
                    delattr(cls, "_singleton_instances")

    @classmethod
    def get_instances(cls):
        """
        Returns a list with all the singleton instances.
        """
        with cls._singleton_lock:
            if hasattr(cls, "_singleton_instances"):
                return getattr(cls, "_singleton_instances").values()
            else:
                return []

    @classmethod
    def referenced_instance(cls, arg):
        """
        Returns True if this singleton instance is referenced.

        Warning: this method uses the GC.get_referrers to determine the number of references.  This
        method is very expensive to use!
        """
        assert hasattr(arg, "__hash__")
        with cls._singleton_lock:
            if hasattr(cls, "_singleton_instances") and arg in getattr(cls, "_singleton_instances"):
                return len(get_referrers(getattr(cls, "_singleton_instances")[arg])) > 1
        return False

    @classmethod
    def reference_instances(cls):
        """
        Returns a list with (reference-count, instance) tuples.

        Warning: this method uses the GC.get_referrers to determine the number of references.  This
        method is very expensive to use!
        """
        with cls._singleton_lock:
            if hasattr(cls, "_singleton_instances"):
                return [(len(get_referrers(instance)) - 2, instance) for instance in getattr(cls, "_singleton_instances").itervalues()]
        return []

    @classmethod
    def sample_reference_instances(cls, size):
        """
        Returns a list with at most SIZE randomly chosen (reference-count, instance) tuples.

        Warning: this method uses the GC.get_referrers to determine the number of references.  This
        method is very expensive to use!
        """
        assert isinstance(size, int)
        assert 0 < size
        with cls._singleton_lock:
            if hasattr(cls, "_singleton_instances"):
                instances = getattr(cls, "_singleton_instances")
                if len(instances) < size:
                    # sample larger than population
                    return [(len(get_referrers(instance)) - 2, instance) for instance in instances.itervalues()]

                else:
                    return [(len(get_referrers(instance)) - 2, instance) for instance in (instances[arg] for arg in sample(instances, size))]

        return []

if __name__ == "__main__":
    from dprint import dprint

    def assert_(value, *args):
        if not value:
            raise AssertionError(*args)

    class Foo(Singleton):
        def __init__(self, message):
            self.message = message

    assert_(not Foo.referenced_instance())

    foo = Foo.get_instance("foo")
    assert_(foo.message == "foo")
    assert_(foo.referenced_instance())

    del foo
    foo = Foo.get_instance("bar")
    assert_(foo.message == "foo")
    assert_(foo.referenced_instance())

    del foo
    assert_(not Foo.referenced_instance())

    Foo.del_instance()
    assert_(not Foo.referenced_instance())

    #
    #
    #

    class Foo(Parameterized1Singleton):
        def __init__(self, key, message):
            self.message = message

        def __eq__(self, other):
            return id(self) == id(other) if isinstance(other, Foo) else self.message == other

    assert_(not Foo.referenced_instance(1))
    assert_(Foo.reference_instances() == [])
    assert_(Foo.sample_reference_instances(10) == [])

    Foo.get_instance(1, "foo")
    assert_(Foo.reference_instances() == [(0, "foo")])
    assert_(Foo.sample_reference_instances(10) == [(0, "foo")])

    foo = Foo.get_instance(1, "foo")
    assert_(foo.message == "foo")
    assert_(foo.referenced_instance(1))
    assert_(Foo.reference_instances() == [(1, "foo")])
    assert_(Foo.sample_reference_instances(10) == [(1, "foo")])

    foo = Foo.get_instance(1, "bar")
    assert_(foo.message == "foo")
    assert_(foo.referenced_instance(1))
    del foo

    assert_(not Foo.referenced_instance(1))
    assert_(Foo.reference_instances() == [(0, "foo")])
    assert_(Foo.sample_reference_instances(10) == [(0, "foo")])

    Foo.del_instance(1)
    assert_(not Foo.referenced_instance(1))
    assert_(Foo.reference_instances() == [])
    assert_(Foo.sample_reference_instances(10) == [])
