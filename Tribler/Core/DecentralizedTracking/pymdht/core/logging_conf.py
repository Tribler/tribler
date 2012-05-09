# Copyright (C) 2009-2010 Raul Jimenez, Arno Bakker
# Released under GNU LGPL 2.1
# See LICENSE.txt for more information

import logging
import logging.handlers
import os

FORMAT = '%(asctime)s %(levelname)s %(filename)s:%(lineno)s - %(funcName)s()\n\
%(message)s\n'

# devnullstream = open(os.devnull,"w")

# logging.basicConfig(level=logging.CRITICAL,
#                    format='%(asctime)s %(levelname)-8s %(message)s',
#                    datefmt='%a, %d %b %Y %H:%M:%S',
#                    stream=devnullstream)


LOG_SIZE_LIMIT_NORMAL = 10 * 2**20 # 10 MB
LOG_SIZE_LIMIT_DEBUG = 2**30 # 1 GB


def testing_setup(module_name):
    logger = logging.getLogger('dht')
    # Arno, 2010-06-11: Alt way of disabling logging from DHT instead of
    # global
    # Raul 2010-11-21: this configuration only affects to tests. It does
    # not affect Tribler/NextShare
    logger.setLevel(logging.DEBUG)
    filename = ''.join((str(module_name), '.log'))
    logger_file = os.path.join('test_logs', filename)
    
    logger_conf = logging.FileHandler(logger_file, 'w')
    logger_conf.setLevel(logging.DEBUG)
    logger_conf.setFormatter(logging.Formatter(FORMAT))
    logger.addHandler(logger_conf)

def setup(logs_path, logs_level):
    logger = logging.getLogger('dht')
    logger.setLevel(logs_level)

    if logs_level == logging.DEBUG:
        log_size_limit = LOG_SIZE_LIMIT_DEBUG
    else:
        log_size_limit = LOG_SIZE_LIMIT_NORMAL
    filename = os.path.join(logs_path, 'pymdht.log')
    logger_conf = logging.handlers.RotatingFileHandler(
        filename, mode='w', maxBytes=log_size_limit, backupCount=0)
    logger_conf.setLevel(logs_level)
    logger_conf.setFormatter(logging.Formatter(FORMAT))
    logger.addHandler(logger_conf)


