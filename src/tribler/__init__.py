import pathlib
import sys


def get_webui_root() -> pathlib.Path:
    """
    Get the location of the "ui" directory.

    When compiled through PyInstaller, the ui directory changes.
    When running from source or when using cx_Freeze, we can use the ``__file__``.
    """
    if hasattr(sys, '_MEIPASS'):
        return pathlib.Path(sys._MEIPASS) / 'ui'  # noqa: SLF001
    return pathlib.Path(__file__).parent.absolute() / "ui"
