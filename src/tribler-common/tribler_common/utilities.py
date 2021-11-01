import os
import re
import sys
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import url2pathname


def is_frozen():
    """
    Return whether we are running in a frozen environment
    """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        sys._MEIPASS
    except Exception:
        return False
    return True


def uri_to_path(uri):
    parsed = urlparse(uri)
    host = "{0}{0}{mnt}{0}".format(os.path.sep, mnt=parsed.netloc)
    return Path(host) / url2pathname(parsed.path)


fts_query_re = re.compile(r'\w+', re.UNICODE)


def to_fts_query(text):
    if not text:
        return ""
    words = fts_query_re.findall(text)
    return ' '.join(f'"{word}"' for word in words) + '*'
