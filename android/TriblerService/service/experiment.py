import os
import ast
import logging
import importlib


class TriblerExperiment(object):


    def __init__(self):
        '''
        Setup environment
        '''
        private_root_dir = os.path.realpath(os.path.split(os.getenv('ANDROID_PRIVATE', '/tmp/cache'))[0])
        os.environ['PYTHON_EGG_CACHE'] = os.path.join(private_root_dir, 'cache', '.egg')

        # Set logging format and level
        logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.WARNING)

        # Executable ffmpeg binary
        os.chmod('ffmpeg', 0744)


    def run(self):
        # Load the module @raises ImportError if module does not load
        m = importlib.import_module(os.getenv('PYTHON_NAME'))

        # Get the class @raises AttributeError if class is not found
        c = getattr(m, os.getenv('PYTHON_NAME'))

        # Get the keyword arguments to run the test with
        kwargs = ast.literal_eval(os.getenv('PYTHON_SERVICE_ARGUMENT', '{}'))

        test = c()
        test.setUp()
        test.runTest(**kwargs)
        test.tearDown()



if __name__ == '__main__':
    TriblerExperiment().run()
