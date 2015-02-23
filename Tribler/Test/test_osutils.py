import os
import sys
import unittest

if os.path.exists('test_osutils.py'):
    BASE_DIR = '..'
    sys.path.insert(1, os.path.abspath('..'))
elif os.path.exists('LICENSE.txt'):
    BASE_DIR = '.'

from Tribler.Core.osutils import fix_filebasename

fix_filebasename


class Test_OsUtils(unittest.TestCase):

    def test_fix_filebasename(self):
        default_name = '_'
        win_name_table = {
            'abcdef': 'abcdef',
          '.': default_name,
          '..': default_name,
          '': default_name,
          ' ': default_name,
          '   ': default_name,
          os.path.join('a', 'b'): 'a_b',
          '\x5c\x61': '_a',    # \x5c = '\\'
          '\x92\x97': '\x92\x97',
          '\x5c\x5c': '__',
          '\x5c\x61\x5c': '_a_',
          '\x2f\x61': '_a',    # \x2f = '/'
          '\x92\x97': '\x92\x97',
          '\x2f\x2f': '__',
          '\x2f\x61\x2f': '_a_',
          'a' * 300: 'a' * 255
        }
        for c in '"*/:<>?\\|':
            win_name_table[c] = default_name

        linux_name_table = {
            'abcdef': 'abcdef',
          '.': default_name,
          '..': default_name,
          '': default_name,
          ' ': default_name,
          '   ': default_name,
          os.path.join('a', 'b'): 'a_b',
          '\x2f\x61': '_a',    # \x2f = '/'
          '\x92\x97': '\x92\x97',
          '\x2f\x2f': '__',
          '\x2f\x61\x2f': '_a_',
          'a' * 300: 'a' * 255
        }

        if sys.platform.startswith('win'):
            name_table = win_name_table
        else:
            name_table = linux_name_table

        for name in name_table:
            fixedname = fix_filebasename(name)
            assert fixedname == name_table[name], (fixedname, name_table[name])
