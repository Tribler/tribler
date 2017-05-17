"""
This file contains a workaround for executing admin-only commands on Windows.
Use only if absolutely necessary!
"""

from ctypes import windll
from os.path import isdir


def mklink(source, target):
    """
    Create a symlink folder ``source``, which links to the folder ``target``.

    :return: whether or not the symlink creation was successful
    :rtype: bool
    """
    succeeded = windll.shell32.ShellExecuteW(None,
                                             u'runas',
                                             u'cmd',
                                             ur'/c mklink /d "%s" "%s"' % (source, target),
                                             None,
                                             0)

    while succeeded and not isdir(source):
        import time
        time.sleep(.05)

    return succeeded
