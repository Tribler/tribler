# Written by Jie Yang
# see LICENSE.txt for license information

import sys
import os
import time
from traceback import print_exc

# To be compatible with Logger from http://linux.duke.edu/projects/mini/logger/ 
# for 2fastbt (revision <=825). 
def create_logger(file_name):
    global logger

    logger = Logger(3, file_name) 


def get_logger():    
    global logger

    if logger is None:
        create_logger("global.log")
        
    return logger


class Logger:
    """
    Atrributes (defulat value):
      threshold (): message will not be logged if its output_level is bigger 
                     than this threshould
      file_name (): log file name
      file_dir ('.'): diectory of log file. It can be absolute or relative path.
      prefix (''): prefix of log file
      prefix_date (False): if it is True, insert 'YYYYMMDD-' between prefix 
                     and file_name, e.g., sp-20060302-buddycast.log given 
                     prefix = 'sp-' and file_name = 'buddycast.log'
      open_mode ('a+b'): mode for open.
    """
    
    def __init__(self, threshold, file_name, file_dir = '.', prefix = '', 
                 prefix_date = False, open_mode = 'a+b'):
         
        self.threshold = threshold            
        if file_name == '':
            self.logfile = sys.stderr
        else:
            try:
                if not os.access(file_dir, os.F_OK):
                    try: 
                        os.mkdir(file_dir)
                    except os.error, msg:
                        raise "logger: mkdir error: " + msg
                file_path = self.get_file_path(file_dir, prefix,
                                               prefix_date, file_name)
                self.logfile = open(file_path, open_mode)
            except Exception, msg:
                self.logfile = None
                print >> sys.stderr, "logger: cannot open log file", \
                         file_name, file_dir, prefix, prefix_date, msg
                print_exc() 
        
    def get_file_path(self, file_dir, prefix, prefix_date, file_name):
        if prefix_date is True:
            date = "%04d%02d%02d"%time.localtime()[:3]
        else:
            date = ''
        return os.path.join(file_dir, prefix + date + file_name)
    
    def log(self, level, msg):
        if level < self.threshold:
            if self.logfile is None: 
                return
            time_stamp = str(time.time())
            self.logfile.write(time_stamp + ' - ')
            if isinstance(msg, str):
                self.logfile.write(msg)
            else:
                self.logfile.write(str(msg))
            self.logfile.write('\n')
            self.logfile.flush()
            

class SuperPeerLogger:
    __single = None
    
    def __init__(self):
        if SuperPeerLogger.__single:
            raise RuntimeError, "SuperPeerLogger is singleton"
        SuperPeerLogger.__single = self

    def getInstance(*args, **kw):
        if SuperPeerLogger.__single is None:
            SuperPeerLogger(*args, **kw)
        return SuperPeerLogger.__single
    getInstance = staticmethod(getInstance)
        
    def log(self, msg):
        pass


class BuddyCastLogger:
    __single = None
    
    def __init__(self):
        if BuddyCastLogger.__single:
            raise RuntimeError, "BuddyCastLogger is singleton"
        BuddyCastLogger.__single = self

    def getInstance(*args, **kw):
        if BuddyCastLogger.__single is None:
            BuddyCastLogger(*args, **kw)
        return BuddyCastLogger.__single
    getInstance = staticmethod(getInstance)
        
    def log(self, msg):
        pass


            
#if __name__ == '__main__':
#    create_logger('test.log')
#    get_logger().log(1, 'abc' + ' ' + str(['abc', 1, (2,3)]))
#    get_logger().log(0, [1,'a',{(2,3):'asfadf'}])
#    get_logger().log(1, open('log').read())
    