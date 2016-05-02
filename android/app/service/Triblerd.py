from kivy.logger import Logger
from kivy.support import install_twisted_reactor

# must be called before importing the reactor
install_twisted_reactor(installSignalHandlers=1) 

from twisted.internet import reactor

import ast
import os
import signal

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
        """
        Pass through options
        """
        options = ast.literal_eval(os.getenv('PYTHON_SERVICE_ARGUMENT'))
        self.start_tribler(options)


    def start_tribler(self, options):
        """
        Main method to startup Tribler.
        """

        def signal_handler(sig, _):
            Logger.info("Received shut down signal %s" % sig)
            if not self._stopping:
                self._stopping = True
                self.session.shutdown()
                Logger.info("Tribler shut down")
                reactor.stop()
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        Logger.info("Starting Tribler")

        config = SessionStartupConfig()
        
        config.set_http_api_enabled(True)
        config.set_http_api_port(options["restapi"])

        self.session = Session(config)
        upgrader = self.session.prestart()
        if upgrader.failed:
            Logger.info("The upgrader failed: .Tribler directory backed up, aborting")
            #reactor.addSystemEventTrigger('after', 'shutdown', os._exit, 1)
            reactor.stop()
        else:
            self.session.start()
            Logger.info("Tribler started")


if __name__ == '__main__':
    Triblerd().run()