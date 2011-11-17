if __debug__:
    from time import time, sleep
    from dprint import dprint

class Constructor(object):
    """
    Allow a class to have multiple constructors.  The right one will
    be chosen based on the parameter types.

    class Foo(Constructor):
        @constructor(int)
        def _init_from_number(self, i):
            pass

        @constructor(str)
        def _init_from_str(self, s):
            pass
    """
    def __new__(cls, *args, **kargs):
        # We only need to get __constructors once per class
        if not hasattr(cls, "_Constructor__constructors"):
            constructors = []
            for m in dir(cls):
                attr = getattr(cls, m)
                if isinstance(attr, tuple) and len(attr) == 4 and attr[0] == "CONSTRUCTOR":
                    _, order, types, method = attr
                    constructors.append((order, types, method))
                    setattr(cls, m, method)
            constructors.sort()
            setattr(cls, "_Constructor__constructors", [(types, method) for _, types, method in constructors])
        return object.__new__(cls)

    def __init__(self, *args, **kargs):
        for types, method in getattr(self, "_Constructor__constructors"):
            if not len(types) == len(args):
                continue
            for type_, arg in zip(types, args):
                if not isinstance(arg, type_):
                    break
            else:
                return method(self, *args, **kargs)
        raise RuntimeError("No constructor found for", tuple(map(type, args)))

__constructor_order = 0
def constructor(*types):
    def helper(func):
        if __debug__:
            # do not do anything when running epydoc
            import sys
            if sys.argv[0] == "(imported)":
                return func
        global __constructor_order
        __constructor_order += 1
        return "CONSTRUCTOR", __constructor_order, types, func
    return helper

def documentation(documented_func):
    def helper(func):
        if documented_func.__doc__:
            prefix = documented_func.__doc__ + "\n"
        else:
            prefix = ""
        func.__doc__ = prefix + "\n        @note: This documentation is copied from " + documented_func.__class__.__name__ + "." + documented_func.__name__
        return func
    return helper

def runtime_duration_warning(threshold):
    assert isinstance(threshold, float), type(threshold)
    assert 0.0 <= threshold
    def helper(func):
        if __debug__:
            def runtime_duration_warning_helper(*args, **kargs):
                start = time()
                try:
                    return func(*args, **kargs)
                finally:
                    end = time()
                    if end - start >= threshold:
                        dprint(func, " took ", "%.2fs" % (end - start), level="warning")
            runtime_duration_warning_helper.__name__ = func.__name__ + "_RDWH"
            return runtime_duration_warning_helper
        else:
            return func
    return helper

if __debug__:
    def main():
        class Foo(Constructor):
            @constructor(int)
            def init_a(self, *args):
                self.init = int
                self.args = args
                self.clss = Foo

            @constructor(int, float)
            def init_b(self, *args):
                self.init = (int, float)
                self.args = args
                self.clss = Foo

            @constructor((str, unicode), )
            def init_c(self, *args):
                self.init = ((str, unicode), )
                self.args = args
                self.clss = Foo

        class Bar(Constructor):
            @constructor(int)
            def init_a(self, *args):
                self.init = int
                self.args = args
                self.clss = Bar

            @constructor(int, float)
            def init_b(self, *args):
                self.init = (int, float)
                self.args = args
                self.clss = Bar

            @constructor((str, unicode), )
            def init_c(self, *args):
                self.init = ((str, unicode), )
                self.args = args
                self.clss = Bar

        foo = Foo(1)
        assert foo.init == int
        assert foo.args == (1, )
        assert foo.clss == Foo

        foo = Foo(1, 1.0)
        assert foo.init == (int, float)
        assert foo.args == (1, 1.0)
        assert foo.clss == Foo

        foo = Foo("a")
        assert foo.init == ((str, unicode), )
        assert foo.args == ("a", )
        assert foo.clss == Foo

        foo = Foo(u"a")
        assert foo.init == ((str, unicode), )
        assert foo.args == (u"a", )
        assert foo.clss == Foo

        bar = Bar(1)
        assert bar.init == int
        assert bar.args == (1, )
        assert bar.clss == Bar

        bar = Bar(1, 1.0)
        assert bar.init == (int, float)
        assert bar.args == (1, 1.0)
        assert bar.clss == Bar

        bar = Bar("a")
        assert bar.init == ((str, unicode), )
        assert bar.args == ("a", )
        assert bar.clss == Bar

        bar = Bar(u"a")
        assert bar.init == ((str, unicode), )
        assert bar.args == (u"a", )
        assert bar.clss == Bar

        def invalid_args(cls, *args):
            try:
                obj = cls(*args)
                assert False
            except RuntimeError:
                pass

        invalid_args(Foo, 1.0)
        invalid_args(Foo, "a", 1)
        invalid_args(Foo, 1, 1.0, 1)
        invalid_args(Foo, [])

        invalid_args(Bar, 1.0)
        invalid_args(Bar, "a", 1)
        invalid_args(Bar, 1, 1.0, 1)
        invalid_args(Bar, [])

        print "Constructor test passed"

        @runtime_duration_warning(1.0)
        def test(delay):
            sleep(delay)

        test(0.5)
        test(1.5)

        print "Runtime duration test complete"

    if __name__ == "__main__":
        main()
