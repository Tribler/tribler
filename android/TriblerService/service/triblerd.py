import os
import logging


class Triblerd(object):


    def __init__(self):
        '''
        Setup environment
        '''
        os.environ['PYTHON_EGG_CACHE'] = os.path.realpath(os.path.join(os.getenv('ANDROID_PRIVATE'), '../cache'))

        # Set logging format and level
        logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.WARNING)

        # Executable ffmpeg binary
        os.chmod('ffmpeg', 0755)


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
