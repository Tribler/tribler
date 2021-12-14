import os
import platform
import re
import sys
from dataclasses import dataclass, field
from typing import Optional, Set, Tuple
from urllib.parse import urlparse
from urllib.request import url2pathname

from tribler_core.utilities.path_util import Path


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
tags_re = re.compile(r'^\s*(?:\[\w+\]\s*)+')


@dataclass
class Query:
    original_query: Optional[str]
    tags: Set[str] = field(default_factory=set)
    fts_text: str = ''


def parse_query(query: Optional[str]) -> Query:
    """
    The query structure:
        query = [tag1][tag2] text
                 ^           ^
                tags        fts query
    """
    if not query:
        return Query(original_query=query)

    tags, tags_string = extract_tags(query)
    fts_text = extract_plain_fts_query_text(query, tags_string)

    return Query(original_query=query, tags=tags, fts_text=fts_text)


def extract_tags(text: Optional[str]) -> Tuple[Set[str], str]:
    if not text:
        return set(), ''
    if (m := tags_re.match(text)) is not None:
        tags = m.group(0).strip()
        return {tag[1:] for tag in tags.split(']') if tag}, m.group(0)
    return set(), ''


def extract_plain_fts_query_text(query: Optional[str], tags_string: str) -> str:
    if query is None:
        return ''

    return query[len(tags_string):].strip()


def to_fts_query(text):
    if not text:
        return None

    words = [f'"{w}"' for w in fts_query_re.findall(text) if w]
    if not words:
        return None

    return ' '.join(words) + '*'


def show_system_popup(title, text):
    """
    Create a native pop-up without any third party dependency.

    :param title: the pop-up title
    :param text: the pop-up body
    """
    sep = "*" * 80

    # pylint: disable=import-outside-toplevel, import-error, broad-except
    print('\n'.join([sep, title, sep, text, sep]), file=sys.stderr)  # noqa: T001
    system = platform.system()
    try:
        if system == 'Windows':
            import win32api

            win32api.MessageBox(0, text, title)
        elif system == 'Linux':
            import subprocess

            subprocess.Popen(['xmessage', '-center', text])
        elif system == 'Darwin':
            import subprocess

            subprocess.Popen(['/usr/bin/osascript', '-e', text])
        else:
            print(f'cannot create native pop-up for system {system}')  # noqa: T001
    except Exception as exception:
        # Use base Exception, because code above can raise many
        # non-obvious types of exceptions:
        # (SubprocessError, ImportError, win32api.error, FileNotFoundError)
        print(f'Error while showing a message box: {exception}')  # noqa: T001
