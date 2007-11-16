import warnings
import os
import sys

if 'DEBUG' in os.environ and os.environ['DEBUG']:
    DEBUG = True
elif 'DEBUG' in sys.argv:
    DEBUG = True
else:
    DEBUG = False

def deprecated(f):
    '''The deprecated decorator will mark a method as deprecated.
    Whenever the method is called a warning will be issued'''
    
    def warning(*args, **kwargs):
        if DEBUG:
            if warning.f.__doc__:
                warnings.warn('"%s" is deprecated. %s' % (warning.f.__name__, warning.f.__doc__), DeprecationWarning, stacklevel=2)
            else:
                warnings.warn('"%s" is deprecated.' % (warning.f.__name__), DeprecationWarning, stacklevel=2)
        return warning.f(*args, **kwargs)
    warning.f = f
    return warning

def arguments(f):
    '''The arguments decorator is a bit of a debug function.
    It displays the function with all it's arguments and the return value'''
    
    def printargs(*args, **kwargs):
        print 'ARGUMENTS: %s(%s)' % (printargs.f.__name__, ', '.join(['%s=%s' % (k, v) for k, v in kwargs.iteritems()] + ['%s' % v for v in args]))
        output = printargs.f(*args, **kwargs)
        print 'OUTPUT:', output
        return output 
    printargs.f = f
    return printargs
