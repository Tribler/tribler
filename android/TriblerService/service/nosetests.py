import os


class TriblerTester(object):


    def __init__(self):
        '''
        Setup environment
        '''
        # Set logging format
        os.environ['NOSE_LOGFORMAT'] = "%(levelname)-7s %(created)d %(module)15s:%(name)s:%(lineno)-4d %(message)s"

        # Executable ffmpeg binary
        os.chmod('ffmpeg', 0755)


    def test(self):
        '''
        Run all tests with nose and xcoverage
        '''
        # The coverage module tries to monkey patch the native _multiprocessing module
        # which is not available on Android
        class _multiprocessing(object):
            pass
        sys.modules["_multiprocessing"] = _multiprocessing

        import coverage
        import nose

        # Switch python working directory to tests directory
        # because --where param does not work correctly on Android
        os.chdir('lib/python2.7/site-packages/Tribler/Test')

        nose.run(argv=os.getenv('PYTHON_SERVICE_ARGUMENT', '').split())



if __name__ == '__main__':
    TriblerTester().test()
