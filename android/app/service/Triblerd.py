from os import getenv

from time import sleep

from Tribler.Core.Session import Session
from Tribler.Core.SessionConfig import SessionStartupConfig


class Triblerd(object):

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

        start_tribler(getenv('PYTHON_SERVICE_ARGUMENT'))


if __name__ == '__main__':
    Triblerd().run()