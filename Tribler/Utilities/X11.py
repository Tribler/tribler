import sys

def init_X11():
    # initialize X11 before wx is imported
    if sys.platform == 'linux2':
        try:
            import ctypes
            x11 = ctypes.cdll.LoadLibrary('libX11.so')
            x11.XInitThreads()
        except OSError as e:
            print >> sys.stderr, "Failed to call XInitThreads '%s'" % str(e)
        except:
            print >> sys.stderr, "Failed to call xInitThreads"
