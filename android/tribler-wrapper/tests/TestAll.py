# coding: utf-8
# Written by Wendo Sabée
# Automatically loads all tests from *_test.py files

import unittest
import os

if __name__ == '__main__':
    # Import all *_test.py files
    for file in os.listdir(os.getcwd()):
        if file.endswith('_test.py'):
            try:
                modulename = file[:len(file) - 3]
                exec("from %s import *" % modulename)
                print "Imported tests from %s" % modulename
            except Exception, e:
                print "Skipped %s (%s)" % (modulename, e)
                pass

    print '\nRunning tests:'

    unittest.main(verbosity=2)