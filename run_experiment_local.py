import sys
import os
import logging
import json
import importlib


class TriblerExperiment(object):


    def __init__(self):
        '''
        Setup environment
        '''
        sys.path.append('./android/TriblerService/service/')

        # Set logging format and level
        logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.WARNING)


    def run(self):
        # Load the module @raises ImportError if module does not load
        m = importlib.import_module(sys.argv[1])

        # Get the class @raises AttributeError if class is not found
        c = getattr(m, sys.argv[1])

        # Get the arguments to run the test with
        args = sys.argv[2:]
        print args

        test = c()
        test.setUp()
        test.runTest(*args)
        test.tearDown()



if __name__ == '__main__':
    TriblerExperiment().run()
