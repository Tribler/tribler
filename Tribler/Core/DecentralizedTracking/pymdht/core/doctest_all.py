# Copyright (C) 2010 Raul Jimenez
# Released under GNU LGPL 2.1
# See LICENSE.txt for more information

"""The reason why this module exists is because nosetests does not
execute doctests correctly.
"""
import os
import doctest
import logging

logger = logging.getLogger(__name__)

EXCEPT = ('doctest_all.py',  # prevents infinite recursion
          'interactive_dht.py',  # is a command, not a module
          'server_dht.py',  # is a command, not a module
          'experiment_dht.py',  # is a command, not a module
          'utils.py'
          )

modnames = sorted([filename[:-3] for filename in os.listdir('.') if
                   filename.endswith('.py')  # *.py only
                 and not filename.startswith('test')  # tests dont have doctests
            and filename not in EXCEPT  # dont include exceptions
                   ])
for modname in modnames:
    if modname.startswith('DEPRECATED'):
        continue
    logger.info('doctesting %s...' % modname)
    mod = __import__(modname)
    failure_count, test_count = doctest.testmod(mod)
    if failure_count:
        logger.info('>>>>>>>>>>>>>>>>>>>>>ERROR<<<<<<<<<<<<<<<<<')
    else:
        logger.info('%d test(s) OK' % test_count)
