'''
Created on Apr 27, 2010

@author: ar
'''
from logging import Handler


class NullHandler(Handler):

    '''
    Useful class that avoids the logging system
    to complain if no logger is configured
    '''
    def emit(self, record):
        pass
