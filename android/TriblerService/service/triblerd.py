import os
import logging


class Triblerd(object):


    def __init__(self):
        '''
        Setup environment
        '''
        private_root_dir = os.path.realpath(os.path.split(os.getenv('ANDROID_PRIVATE', '/tmp/cache'))[0])
        os.environ['PYTHON_EGG_CACHE'] = os.path.join(private_root_dir, 'cache', '.egg')

        # Set logging format and level
        logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.ERROR)

        # Executable ffmpeg binary
        os.chmod('ffmpeg', 0744)


    def run(self):
        '''
        Start reactor with service argument
        '''
        from twisted.internet import reactor
        from twisted.plugins.tribler_plugin import Options, service_maker

        options = Options()
        Options.parseOptions(options, os.getenv('PYTHON_SERVICE_ARGUMENT', '').split())
        service_maker.makeService(options)
        reactor.run()



if __name__ == '__main__':
    Triblerd().run()
