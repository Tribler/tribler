# Written by Jie Yang
# see LICENSE.txt for license information

import sys
import os
import time
import socket
from traceback import print_exc
from base64 import encodestring
from sha import sha
            
DEBUG = False

log_separator = ' - '

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


def get_today():    # UTC based
    return time.gmtime(time.time())[:3]

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
                
    def __del__(self):
        self.close()
        
    def get_file_path(self, file_dir, prefix, prefix_date, file_name):
        if prefix_date is True:    # create a new file for each day
            today = get_today()
            date = "%04d%02d%02d" % today
        else:
            date = ''
        return os.path.join(file_dir, prefix + date + file_name)
    
    def log(self, level, msg):
        if level <= self.threshold:
            if self.logfile is None: 
                return
            time_stamp = "%.03f"%time.time()
            self.logfile.write(time_stamp + log_separator)
            if isinstance(msg, str):
                self.logfile.write(msg)
            else:
                self.logfile.write(repr(msg))
            self.logfile.write('\n')
            self.logfile.flush()
            
    def close(self):
        if self.logfile is not None:
            self.logfile.close()
            

class OverlayLogger:
    __single = None
    
    def __init__(self, file_name, file_dir = '.'):
        if OverlayLogger.__single:
            raise RuntimeError, "OverlayLogger is singleton"
        self.file_name = file_name
        self.file_dir = file_dir
        OverlayLogger.__single = self

    def getInstance(*args, **kw):
        if OverlayLogger.__single is None:
            OverlayLogger(*args, **kw)
        return OverlayLogger.__single
    getInstance = staticmethod(getInstance)
        
    def log(self, *msgs):
        log_msg = ''
        nmsgs = len(msgs)
        if nmsgs == 0:
            return
        else:
            for i in range(nmsgs-1):
                log_msg += msgs[i]
                log_msg += log_separator
            if msgs[nmsgs-1]:
                log_msg += msgs[nmsgs-1]
        if log_msg:
            if DEBUG:
                db_msg = ''
                if msgs[0].endswith('MSG'):
                    for i in range(nmsgs-2):
                        db_msg += msgs[i]
                        db_msg += log_separator
                    permid = msgs[nmsgs-2]
                    s = encodestring(permid).replace("\n","")
                    db_msg += encodestring(sha(s).digest()).replace("\n","")
                else:
                    for i in range(nmsgs-1):
                        db_msg += msgs[i]
                        db_msg += log_separator
                    permid = msgs[nmsgs-1]
                    s = encodestring(permid).replace("\n","")
                    db_msg += encodestring(sha(s).digest()).replace("\n","")
                print >> sys.stderr, "Logger: ", db_msg
            self.write_log(log_msg)
        
    def write_log(self, msg):
        # one logfile per day. 
        today = get_today()
        if not hasattr(self, 'today'):
            self.today = today
            self.logger = self.make_logger()
        elif today != self.today:    # make a new log if a new day comes
            self.logger.close()
            self.logger = self.make_logger()
        self.logger.log(3, msg)
            
    def make_logger(self):
        hostname = socket.gethostname()
        return Logger(3, self.file_name, self.file_dir, hostname, True)
        
            
if __name__ == '__main__':
    create_logger('test.log')
    get_logger().log(1, 'abc' + ' ' + str(['abc', 1, (2,3)]))
    get_logger().log(0, [1,'a',{(2,3):'asfadf'}])
    #get_logger().log(1, open('log').read())
    