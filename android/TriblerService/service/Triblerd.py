import os


class Triblerd(object):

    def __init__(self):
        '''
        Setup environment
        '''
        private_root_dir = os.path.realpath(os.path.split(os.getenv('ANDROID_PRIVATE', '/tmp/cache'))[0])
        os.environ['PYTHON_EGG_CACHE'] = os.path.join(private_root_dir, 'cache', '.egg')

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
        Run all tests with nose
        '''
        import nose

        os.chdir('lib/python2.7/site-packages/Tribler/Test')
        nose.run(argv=['--nocapture', '--nologcapture', '--verbose', '--stop'])


if __name__ == '__main__':
    Triblerd().run()