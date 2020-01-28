from __future__ import absolute_import

import pathlib
import sys
import tempfile
import urllib
from shutil import rmtree


class Path(type(pathlib.Path())):

    def rmtree(self, ignore_errors=False, onerror=None):
        """
        Delete the entire directory even if it contains directories / files.
        """
        rmtree(str(self), ignore_errors, onerror)

    def startswith(self, text):
        return self.match("%s*" % text)

    def endswith(self, text):
        return self.match("*%s" % text)

    def to_text(self):
        return str(self)


class PosixPath(Path, pathlib.PurePosixPath):
    __slots__ = ()


class WindowsPath(Path, pathlib.PureWindowsPath):
    __slots__ = ()


def abspath(path, optional_prefix=None):
    path = Path(path)
    return path if path.is_absolute() else Path(optional_prefix, path) if optional_prefix else path.absolute()


def norm_path(base_path, path):
    base_path = Path(base_path)
    path = Path(path)
    if path.is_absolute():
        if base_path.resolve() in list(path.resolve().parents):
            return path.relative_to(base_path)
    return path

def normpath(input):
    return Path(input).resolve()


def join(*path):
    return Path(*path)


def makedirs(directory):
    Path(directory).mkdir(parents=True)

def isabs(input):
    return Path(input).is_absolute()

def issubfolder(base_path, path):
    return base_path in list(path.parents)

def realpath(input):
    return Path(input).resolve()

def expanduser(input):
    return Path(input).expanduser()

def split(input):
    p = Path(input)
    return p.parent, p.name

def basename(input):
    return Path(input).name

def getsize(input):
    return Path(input).stat().st_size

def mkdtemp(*args, **kwargs):
    return Path(tempfile.mkdtemp(*args, **kwargs))

def pathname2url(input):
    return urllib.request.pathname2url(str(input))


def str_path(path):
    """"
    String representation of Path-like object with work around for Windows long filename issue.
    """
    if sys.platform == 'win32':
        return "\\\\?\\" + str(path)
    return str(path)
