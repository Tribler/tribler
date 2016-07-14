import os
import sys


class Triblerd(object):


    def __init__(self):
        '''
        Setup environment
        '''
        private_root_dir = os.path.realpath(os.path.split(os.getenv('ANDROID_PRIVATE', '/tmp/cache'))[0])
        os.environ['PYTHON_EGG_CACHE'] = os.path.join(private_root_dir, 'cache', '.egg')

        # Executable ffmpeg binary
        os.chmod('ffmpeg', 0744)


    def run(self):
        '''
        Start reactor with service argument
        '''
        import logging
        from twisted.internet import reactor
        from twisted.plugins.tribler_plugin import Options, service_maker

        # Set logging format and level
        logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.ERROR)

        options = Options()
        Options.parseOptions(options, os.getenv('PYTHON_SERVICE_ARGUMENT', '').split())
        service_maker.makeService(options)
        reactor.run()


    def profile(self):
        '''
        Run in profile mode, dumping results to file
        '''
        import logging
        import time
        from twisted.python import log
        from twisted.scripts.twistd import run
        from twisted.internet import reactor

        def gracefull_shutdown():
            '''
            Write profiler results to file and stop the reactor
            '''
            # TODO: dump profiler results
            reactor.stop()

        reactor.callLater(10 * 60, gracefull_shutdown)

        # Override twisted logging
        #observer = log.PythonLoggingObserver()
        #observer.start()

        # Set logging format and level
        logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.CRITICAL)

        # Pass through service arguments to tribler
        sys.argv += ['-n', '--profile=profile_' + str(time.time()) + '.cprofile', 'tribler']
        sys.argv += os.getenv('PYTHON_SERVICE_ARGUMENT', '').split()
        run()


    def test(self):
        '''
        Run all tests with nose and xcoverage
        '''
        # The coverage module tries to monkey patch the native _multiprocessing module
        # which is not available on Android
        class _multiprocessing(object):
            pass
        sys.modules["_multiprocessing"] = _multiprocessing

        import shutil
        import coverage
        import nose

        # Clean output directory
        OUTPUT_DIR = os.path.abspath('output')
        if os.path.exists(OUTPUT_DIR):
            shutil.rmtree(OUTPUT_DIR, ignore_errors=True)
        os.mkdir(OUTPUT_DIR)

        # Switch python working directory to tests directory
        # because --where param does not work correctly on Android
        os.chdir('lib/python2.7/site-packages/Tribler/Test')

        # From https://raw.githubusercontent.com/Tribler/gumby/devel/scripts/run_nosetests_for_jenkins.sh
        NOSEARGS_COMMON = "--with-xunit --all-modules --traverse-namespace --cover-package=Tribler --cover-tests --cover-inclusive"
        NOSEARGS = "--verbose --with-xcoverage --xcoverage-file=" + OUTPUT_DIR + "/coverage.xml --xunit-file=" + OUTPUT_DIR + "/nosetests.xml " + NOSEARGS_COMMON

        # Set logging format
        os.environ['NOSE_LOGFORMAT'] = "%(levelname)-7s %(created)d %(module)15s:%(name)s:%(lineno)-4d %(message)s"

        nose.run(argv=NOSEARGS.split())


    def experiment(self):
        '''
        Run performance experiment for multichain blocks
        '''
        from experiment_multichain_scale import TestMultiChainScale

        test = TestMultiChainScale()
        test.setUp()
        test.runTest(blocks_in_thousands=10)
        test.tearDown()


if __name__ == '__main__':
    Triblerd().profile()
