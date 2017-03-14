import os
import sys

if os.path.exists('test_osutils.py'):
    BASE_DIR = '..'
    sys.path.insert(1, os.path.abspath('..'))
elif os.path.exists('LICENSE'):
    BASE_DIR = '.'

from Tribler.Core.osutils import (fix_filebasename, is_android, get_home_dir, get_appstate_dir, get_picture_dir,
                                  get_desktop_dir)
from Tribler.Test.test_as_server import BaseTestCase


class Test_OsUtils(BaseTestCase):

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

    def test_is_android(self):
        if sys.platform.startswith('linux') and 'ANDROID_PRIVATE' in os.environ:
            self.assertTrue(is_android())
        else:
            self.assertFalse(is_android())

    def test_home_dir(self):
        home_dir = get_home_dir()
        self.assertIsInstance(home_dir, unicode)
        self.assertTrue(os.path.isdir(home_dir))

    def test_appstate_dir(self):
        appstate_dir = get_appstate_dir()
        self.assertIsInstance(appstate_dir, unicode)
        self.assertTrue(os.path.isdir(appstate_dir))

    def test_picture_dir(self):
        picture_dir = get_picture_dir()
        self.assertIsInstance(picture_dir, unicode)
        self.assertTrue(os.path.isdir(picture_dir))

    def test_desktop_dir(self):
        desktop_dir = get_desktop_dir()
        self.assertIsInstance(desktop_dir, unicode)
        self.assertTrue(os.path.isdir(desktop_dir))
