import os
import ast

from time import sleep

from kivy.logger import Logger

from Tribler.Core.Session import Session
from Tribler.Core.SessionConfig import SessionStartupConfig


class Triblerd(object):

    def __init__(self):
        """
        Setup environment
        """
        private_root_dir = os.path.realpath(os.path.split(os.environ['ANDROID_PRIVATE'])[0])
        os.environ['PYTHON_EGG_CACHE'] = os.path.join(private_root_dir, 'cache', '.egg')


    def run(self):

        def start_tribler(options):
            config = SessionStartupConfig()
            config.set_http_api_enabled(True)
            config.set_http_api_port(options['restapi'])

            self.session = Session(config)

            Logger.info('Run upgrader...')
            upgrader = self.session.prestart()

            if upgrader.failed:
                Logger.error('The upgrader failed')
            else:
                Logger.info('Starting Tribler...')
                self.session.start()
                Logger.info('Tribler started!')

        """
        Pass through options
        """
        options = ast.literal_eval(os.getenv('PYTHON_SERVICE_ARGUMENT'))
        start_tribler(options)


if __name__ == '__main__':
    Triblerd().run()