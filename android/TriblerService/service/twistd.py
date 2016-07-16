import os
import sys
import logging


class Twistd(object):


    def __init__(self):
        '''
        Setup environment
        '''
        private_root_dir = os.path.realpath(os.path.split(os.getenv('ANDROID_PRIVATE', '/tmp/cache'))[0])
        os.environ['PYTHON_EGG_CACHE'] = os.path.join(private_root_dir, 'cache', '.egg')

        # Set logging format and level
        logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.CRITICAL)

        # Executable ffmpeg binary
        os.chmod('ffmpeg', 0744)


    def profile(self):
        '''
        Run in profile mode, dumping results to file
        '''
        import logging
        #from twisted.python import log
        from twisted.scripts.twistd import run
        from twisted.internet import reactor

        def gracefull_shutdown():
            '''
            Profiler results are written to file on reactor stop
            '''
            reactor.stop()

        reactor.callLater(10 * 60, gracefull_shutdown)

        # Override twisted logging
        #observer = log.PythonLoggingObserver()
        #observer.start()

        # Pass through service arguments
        sys.argv += os.getenv('PYTHON_SERVICE_ARGUMENT', '').split()
        run()



if __name__ == '__main__':
    Twistd().profile()
