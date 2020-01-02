import os
import shutil
import sys

from tribler_core.tests.tools.test_as_server import BaseTestCase
from tribler_core.utilities import path_util
from tribler_core.utilities.osutils import (
    dir_copy,
    fix_filebasename,
    get_appstate_dir,
    get_desktop_dir,
    get_home_dir,
    get_picture_dir,
    is_android,
)
from tribler_core.utilities.path_util import mkdtemp

if os.path.exists('test_osutils.py'):
    BASE_DIR = '..'
    sys.path.insert(1, os.path.abspath('..'))
elif os.path.exists('LICENSE'):
    BASE_DIR = '.'



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
            self.assertEqual(fixedname, name_table[name])

    def test_is_android(self):
        if sys.platform.startswith('linux') and 'ANDROID_PRIVATE' in os.environ:
            self.assertTrue(is_android())
        else:
            self.assertFalse(is_android())

    def test_home_dir(self):
        home_dir = get_home_dir()
        self.assertIsInstance(home_dir, path_util.Path)
        self.assertTrue(home_dir.is_dir())

    def test_appstate_dir(self):
        appstate_dir = get_appstate_dir()
        self.assertIsInstance(appstate_dir, path_util.Path)
        self.assertTrue(appstate_dir.is_dir())

    def test_picture_dir(self):
        picture_dir = get_picture_dir()
        self.assertIsInstance(picture_dir, path_util.Path)
        self.assertTrue(picture_dir.is_dir())

    def test_desktop_dir(self):
        desktop_dir = get_desktop_dir()
        self.assertIsInstance(desktop_dir, path_util.Path)
        self.assertTrue(desktop_dir.is_dir())

    def test_dir_copy(self):
        """
        Tests copying a source directory to destination directory.
        """
        temp_dir = mkdtemp()
        src_dir = temp_dir / 'src'
        dest_dir = temp_dir / 'dest'

        src_sub_dirs = ['dir1', 'dir2', 'dir3']
        os.makedirs(src_dir)
        for sub_dir in src_sub_dirs:
            os.makedirs(src_dir / sub_dir)
        self.assertGreater(len(os.listdir(src_dir)), 1)

        dir_copy(src_dir, dest_dir)

        self.assertEqual(len(os.listdir(dest_dir)), len(os.listdir(src_dir)))

        shutil.rmtree(temp_dir, ignore_errors=True)
