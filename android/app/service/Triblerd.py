from time import sleep

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

        def start_tribler(arg):
            self.session = Session(SessionStartupConfig())
            upgrader = self.session.prestart()
            while not upgrader.is_done:
                sleep(0.1)
            self.session.start()

            while not self.session.lm.initComplete:
                sleep(0.2)

            while True:
                sleep(1)

        start_tribler(os.getenv('PYTHON_SERVICE_ARGUMENT'))


if __name__ == '__main__':
    Triblerd().run()