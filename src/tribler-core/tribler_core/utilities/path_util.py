from __future__ import annotations

import pathlib
import sys
import tempfile


class Path(type(pathlib.Path())):
    @staticmethod
    def mkdtemp(*args, **kwargs) -> Path:
        return Path(tempfile.mkdtemp(*args, **kwargs))

    @staticmethod
    def fix_win_long_file(path: Path):
        """"
        String representation of Path-like object with work around for Windows long filename issue.
        """
        if sys.platform == 'win32':
            return "\\\\?\\" + str(path)
        return str(path)

    def normalize_to(self, base: str = None) -> Path:
        """Return a relative path if 'self' is relative to base.
        Return an absolute path overwise.
        """
        if base is None:
            return self
        try:
            return self.relative_to(Path(base))
        except ValueError:
            pass

        return self

    def size(self) -> int:
        return self.stat().st_size

    def startswith(self, text: str) -> bool:
        return self.match(f"{text}*")

    def endswith(self, text: str) -> bool:
        return self.match(f"*{text}")


class PosixPath(Path, pathlib.PurePosixPath):
    __slots__ = ()


class WindowsPath(Path, pathlib.PureWindowsPath):
    __slots__ = ()
