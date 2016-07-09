import os
from shutil import rmtree


class Triblerd(object):

    def __init__(self):
        '''
        Setup environment
        '''
        private_root_dir = os.path.realpath(os.path.split(os.getenv('ANDROID_PRIVATE', '/tmp/cache'))[0])
        os.environ['PYTHON_EGG_CACHE'] = os.path.join(private_root_dir, 'cache', '.egg')

        # Executable ffmpeg binary
        os.chmod("ffmpeg", 0744)

    def run(self):
        '''
        Start reactor with service argument
        '''
        from twisted.internet import reactor

        from tribler_plugin import service_maker, Options

        options = Options()
        Options.parseOptions(options, os.getenv('PYTHON_SERVICE_ARGUMENT', '').split())
        service_maker.makeService(options)
        reactor.run()

    def test(self):
        '''
        Run all tests with nose and xcoverage
        '''
        # Mock native _multiprocessing module
        class _multiprocessing(object):
            pass
        import sys
        sys.modules["_multiprocessing"] = _multiprocessing

        import coverage
        import nose

        # Switch to Test directory
        os.chdir('lib/python2.7/site-packages/Tribler/Test')
        
        # Clean output directory
        OUTPUT_DIR = os.path.abspath('output')
        if os.path.exists(OUTPUT_DIR):
            rmtree(OUTPUT_DIR, ignore_errors=True)
        os.mkdir(OUTPUT_DIR)
        
        # From https://raw.githubusercontent.com/Tribler/gumby/devel/scripts/run_nosetests_for_jenkins.sh
        NOSEARGS_COMMON = "--with-xunit --all-modules --traverse-namespace --cover-package=Tribler --cover-tests --cover-inclusive"
        NOSEARGS = "--verbose --with-xcoverage --xcoverage-file=" + OUTPUT_DIR + "/coverage.xml --xunit-file=" + OUTPUT_DIR + "/nosetests.xml.part " + NOSEARGS_COMMON

        os.environ['NOSE_LOGFORMAT'] = "%(levelname)-7s %(created)d %(module)15s:%(name)s:%(lineno)-4d %(message)s"

        nose.run(argv=NOSEARGS.split())  # --nocapture --nologcapture


if __name__ == '__main__':
    Triblerd().run()
