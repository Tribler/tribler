import os
import sys
from pathlib import Path

from tribler_core.utilities.osutils import (
    dir_copy,
    fix_filebasename,
    get_appstate_dir,
    get_desktop_dir,
    get_home_dir,
    get_picture_dir,
    is_android,
)

if os.path.exists('test_osutils.py'):
    BASE_DIR = '..'
    sys.path.insert(1, os.path.abspath('..'))
elif os.path.exists('LICENSE'):
    BASE_DIR = '.'


def test_fix_filebasename():
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
        assert fixedname == name_table[name]


def test_is_android():
    if sys.platform.startswith('linux') and 'ANDROID_PRIVATE' in os.environ:
        assert is_android()
    else:
        assert not is_android()


def test_home_dir():
    home_dir = get_home_dir()
    assert isinstance(home_dir, Path)
    assert home_dir.is_dir()


def test_appstate_dir():
    appstate_dir = get_appstate_dir()
    assert isinstance(appstate_dir, Path)
    assert appstate_dir.is_dir()


def test_picture_dir():
    picture_dir = get_picture_dir()
    assert isinstance(picture_dir, Path)
    assert picture_dir.is_dir()


def test_desktop_dir():
    desktop_dir = get_desktop_dir()
    assert isinstance(desktop_dir, Path)
    assert desktop_dir.is_dir()


def test_dir_copy(tmpdir):
    """
    Tests copying a source directory to destination directory.
    """
    # Source directory with some sub directories
    src_dir = os.path.join(tmpdir, 'src')
    src_sub_dirs = ['dir1', 'dir2', 'dir3']
    os.makedirs(src_dir)
    for sub_dir in src_sub_dirs:
        os.makedirs(os.path.join(src_dir, sub_dir))
    dummy_file = "dummy.txt"
    Path(src_dir, dummy_file).write_text("source: hello world")
    assert len(os.listdir(src_dir)) > 1

    # Destination directories
    dest_dir1 = os.path.join(tmpdir, 'dest1')  # will not exist initially; to test dir copy
    dest_dir2 = os.path.join(tmpdir, 'dest2')  # will be created; to test dir merge

    os.makedirs(dest_dir2)  # create some files inside
    Path(dest_dir2, dummy_file).write_text("dest: hello world")
    assert len(os.listdir(dest_dir2)) == 1

    # Copy source directory to non-existent destination directory; should work
    dir_copy(src_dir, dest_dir1)
    assert len(os.listdir(dest_dir1)) == len(os.listdir(src_dir))

    # Copy source directory to already existing destination directory
    dir_copy(src_dir, dest_dir2, merge_if_exists=False)
    assert len(os.listdir(dest_dir2)) == 1  # nothing copied
    # Try copying with merge flag set
    dir_copy(src_dir, dest_dir2, merge_if_exists=True)
    assert len(os.listdir(src_dir)) == len(os.listdir(dest_dir2))
    assert Path(dest_dir2, dummy_file).read_text() == "source: hello world"
