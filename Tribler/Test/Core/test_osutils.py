from __future__ import absolute_import

import os
import shutil
import sys
import tempfile
from pathlib import Path

import six

if os.path.exists('test_osutils.py'):
    BASE_DIR = '..'
    sys.path.insert(1, os.path.abspath('..'))
elif os.path.exists('LICENSE'):
    BASE_DIR = '.'

from Tribler.Core.osutils import (dir_copy, fix_filebasename, get_appstate_dir, get_desktop_dir, get_home_dir,
                                  get_picture_dir, is_android)
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
        self.assertIsInstance(home_dir, six.text_type)
        self.assertTrue(os.path.isdir(home_dir))

    def test_appstate_dir(self):
        appstate_dir = get_appstate_dir()
        self.assertIsInstance(appstate_dir, six.text_type)
        self.assertTrue(os.path.isdir(appstate_dir))

    def test_picture_dir(self):
        picture_dir = get_picture_dir()
        self.assertIsInstance(picture_dir, six.text_type)
        self.assertTrue(os.path.isdir(picture_dir))

    def test_desktop_dir(self):
        desktop_dir = get_desktop_dir()
        self.assertIsInstance(desktop_dir, six.text_type)
        self.assertTrue(os.path.isdir(desktop_dir))

    def test_dir_copy(self):
        """
        Tests copying a source directory to destination directory.
        """
        temp_dir = tempfile.mkdtemp()

        # Source directory with some sub directories
        src_dir = os.path.join(temp_dir, 'src')
        src_sub_dirs = ['dir1', 'dir2', 'dir3']
        os.makedirs(src_dir)
        for sub_dir in src_sub_dirs:
            os.makedirs(os.path.join(src_dir, sub_dir))
        Path(src_dir, "test.txt").write_text("source: hello world")
        self.assertGreater(len(os.listdir(src_dir)), 1)

        # Destination directories
        dest_dir1 = os.path.join(temp_dir, 'dest1')  # will not exist initially; to test dir copy
        dest_dir2 = os.path.join(temp_dir, 'dest2')  # will be created; to test dir merge

        os.makedirs(dest_dir2)  # create some files inside
        Path(dest_dir2, "test.txt").write_text("dest: hello world")
        self.assertEqual(len(os.listdir(dest_dir2)), 1)

        # Copy source directory to non-existent destination directory; should work
        dir_copy(src_dir, dest_dir1)
        self.assertEqual(len(os.listdir(dest_dir1)), len(os.listdir(src_dir)))

        # Copy source directory to already existing destination directory
        dir_copy(src_dir, dest_dir2, merge_if_exists=False)
        self.assertEqual(len(os.listdir(dest_dir2)), 1)  # nothing copied
        # Try copying with merge flag set
        dir_copy(src_dir, dest_dir2, merge_if_exists=True)
        self.assertEqual(len(os.listdir(src_dir)), len(os.listdir(dest_dir2)))
        self.assertEqual(Path(dest_dir2, "test.txt").read_text(), "source: hello world")
        shutil.rmtree(temp_dir, ignore_errors=True)
