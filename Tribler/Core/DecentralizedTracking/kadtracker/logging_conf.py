# Copyright (C) 2009 Raul Jimenez
# Released under GNU LGPL 2.1
# See LICENSE.txt for more information

import logging
import os

FORMAT = '%(asctime)s %(levelname)s %(filename)s:%(lineno)s - %(funcName)s()\n\
%(message)s\n'

def setup(logs_path, logs_level):
    logging.basicConfig(level=logs_level,
                        format=FORMAT,
                        filename= os.path.join(logs_path,
                                               'dht_debug.log'),
                        filemode='w')

    info_log = logging.FileHandler(
        os.path.join(logs_path, 'dht_info.log'), 'w')
    info_log.setLevel(logging.INFO)
    info_log.setFormatter(logging.Formatter(FORMAT))
    logging.getLogger('').addHandler(info_log)

    warning_log = logging.FileHandler(
        os.path.join(logs_path, 'dht_warning.log'), 'w')
    warning_log.setLevel(logging.WARNING)
    warning_log.setFormatter(logging.Formatter(FORMAT))
    loggging.getLogger('').addHandler(warning_log)
