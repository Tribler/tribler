import os


class TriblerTester(object):


    def __init__(self):
        '''
        Setup environment
        '''
        private_root_dir = os.path.realpath(os.path.split(os.getenv('ANDROID_PRIVATE', '/tmp/cache'))[0])
        os.environ['PYTHON_EGG_CACHE'] = os.path.join(private_root_dir, 'cache', '.egg')

        # Set logging format
        os.environ['NOSE_LOGFORMAT'] = "%(levelname)-7s %(created)d %(module)15s:%(name)s:%(lineno)-4d %(message)s"

        # Executable ffmpeg binary
        os.chmod('ffmpeg', 0744)


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
