"""
Child File Descriptors are only supported by Twisted for Linux.
If support is added for other platforms, add them to CHILDFDS_ENABLED.
Possible values are (see platform.system):
    - 'Linux'
    - 'Windows'
    - 'Java'
    - ''
"""

from platform import system

CHILDFDS_ENABLED = system() in ['Linux',]

# Set the Windows IO streams to binary mode
try:
    import msvcrt # Import error if not on Windows
    import os, sys
    msvcrt.setmode(sys.stdin.fileno(), os.O_BINARY)
    msvcrt.setmode(sys.stdout.fileno(), os.O_BINARY)
    msvcrt.setmode(sys.stderr.fileno(), os.O_BINARY)
    os.environ['PYTHONUNBUFFERED'] = '1'
except ImportError:
    pass
