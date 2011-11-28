# Written by Jie Yang
# see LICENSE.txt for license information
#
# Log version 3 = BuddyCast message V8

import sys
import os
import time
import socket
import threading
from traceback import print_exc
            
DEBUG = False

log_separator = ' '
logger = None

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
      file_dir ('.'): directory of log file. It can be absolute or relative path.
      prefix (''): prefix of log file
      prefix_date (False): if it is True, insert 'YYYYMMDD-' between prefix 
                     and file_name, e.g., sp-20060302-buddycast.log given 
                     prefix = 'sp-' and file_name = 'buddycast.log'
      open_mode ('a+b'): mode for open.
    """
    
    def __init__(self, threshold, file_name, file_dir = '.', prefix = '', 
                 prefix_date = False, open_mode = 'a+b'):
        
        self.threshold = threshold            
        self.Log = self.log
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
    
    def log(self, level, msg, showtime=True):
        if level <= self.threshold:
            if self.logfile is None: 
                return
            if showtime:
                time_stamp = "%.01f"%time.time()
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
    __lock = threading.RLock()
    
    def __init__(self, file_name, file_dir = '.'):
        if OverlayLogger.__single:
            raise RuntimeError, "OverlayLogger is singleton2"
        
        self.file_name = file_name
        self.file_dir = file_dir
        OverlayLogger.__single = self
        self.Log = self.log
        self.__call__ = self.log

    def getInstance(*args, **kw):
        OverlayLogger.__lock.acquire()
        try:
            if OverlayLogger.__single is None:
                OverlayLogger(*args, **kw)
            return OverlayLogger.__single
        finally:
            OverlayLogger.__lock.release()
    getInstance = staticmethod(getInstance)
    
    def log(self, *msgs):
        """
        # MSG must be the last one. Permid should be in the rear to be readable
        BuddyCast log for superpeer format: (V2)    
          CONN_TRY IP PORT PERMID
          CONN_ADD IP PORT PERMID SELVERSION
          CONN_DEL IP PORT PERMID REASON
          SEND_MSG IP PORT PERMID SELVERSION MSG_ID MSG
          RECV_MSG IP PORT PERMID SELVERSION MSG_ID MSG
          
          #BUCA_CON Permid1, Permid2, ...
          
          BUCA_STA xx xx xx ...    # BuddyCast status
              1  Pr    # nPeer
              2  Pf    # nPref
              3  Tr    # nTorrent
              
              #4  Cc    # nConntionCandidates (this one was missed before v4.1, and will not be included either in this version)
              4  Bs    # nBlockSendList
              5  Br    # nBlockRecvList
              
              6  SO    # nConnectionsInSecureOver
              7  Co    # nConnectionsInBuddyCast
              
              8  Ct    # nTasteConnectionList
              9  Cr   # nRandomConnectionList
              10  Cu   # nUnconnectableConnectionList


        Dispersy logs with a slightly modified format
          CONN_TRY COMMUNITY IP PORT
          CONN_ADD COMMUNITY IP PORT PERMID DISPERSY-VERSION COMMUNITY-VERSION
          CONN_DEL COMMUNITY IP PORT
        Where:
          COMMUNITY is the HEX encoded sha1 of the master member public key
          IP is the host in www.xxx.yyy.zzz
          PORT is the host port
          PERMID is the HEX encoded public key of the member
          DISPERSY-VERSION is the HEX encoded dispersy version (first byte in packet)
          COMMUNITY-VERSION is the HEX encoded community version (second byte in packet)
          """
        
        log_msg = ''
        nmsgs = len(msgs)
        if nmsgs < 2:
            print >> sys.stderr, "Error message for log", msgs
            return
        
        else:
            for i in range(nmsgs):
                if isinstance(msgs[i], tuple) or isinstance(msgs[i], list):
                    log_msg += log_separator
                    for msg in msgs[i]:
                        try:
                            log_msg += str(msg)
                        except:
                            log_msg += repr(msg)
                        log_msg += log_separator
                else:
                    try:
                        log_msg += str(msgs[i])
                    except:
                        log_msg += repr(msgs[i])
                    log_msg += log_separator
                
        if log_msg:
            self._write_log(log_msg)
        
    def _write_log(self, msg):
        # one logfile per day. 
        today = get_today()
        if not hasattr(self, 'today'):
            self.logger = self._make_logger(today)
        elif today != self.today:    # make a new log if a new day comes
            self.logger.close()
            self.logger = self._make_logger(today)
        self.logger.log(3, msg)
            
    def _make_logger(self, today):
        self.today = today
        hostname = socket.gethostname()
        logger = Logger(3, self.file_name, self.file_dir, hostname, True)
        logger.log(3, '# Tribler Overlay Log Version 3', showtime=False)    # mention the log version at the first line
        logger.log(3, '# BUCA_STA: nRound   nPeer nPref nTorrent   ' + \
                   'nBlockSendList nBlockRecvList   ' + \
                   'nConnectionsInSecureOver nConnectionsInBuddyCast  ' + \
                   'nTasteConnectionList nRandomConnectionList nUnconnectableConnectionList', 
                   showtime=False)
        logger.log(3, '# BUCA_STA: Rd  Pr Pf Tr  Bs Br  SO Co  Ct Cr Cu', showtime=False)
        return logger
        
if __name__ == '__main__':
    create_logger('test.log')
    get_logger().log(1, 'abc' + ' ' + str(['abc', 1, (2,3)]))
    get_logger().log(0, [1,'a',{(2,3):'asfadf'}])
    #get_logger().log(1, open('log').read())
    
    ol = OverlayLogger('overlay.log')
    ol.log('CONN_TRY', '123.34.3.45', 34, 'asdfasdfasdfasdfsadf')
    ol.log('CONN_ADD', '123.34.3.45', 36, 'asdfasdfasdfasdfsadf', 3)
    ol.log('CONN_DEL', '123.34.3.45', 38, 'asdfasdfasdfasdfsadf', 'asbc')
    ol.log('SEND_MSG', '123.34.3.45', 39, 'asdfasdfasdfasdfsadf', 2, 'BC', 'abadsfasdfasf')
    ol.log('RECV_MSG', '123.34.3.45', 30, 'asdfasdfasdfasdfsadf', 3, 'BC', 'bbbbbbbbbbbbb')
    ol.log('BUCA_STA', (1,2,3), (4,5,6), (7,8), (9,10,11))
    ol.log('BUCA_CON', ['asfd','bsdf','wevs','wwrewv'])
    
