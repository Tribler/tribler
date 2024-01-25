"""
This module mainly provides validation and correction for urls. This class
provides a method for HTTP GET requests as well as a function to translate peers into health.
Author(s): Jie Yang
"""
import itertools
import logging
import os
import platform
import random
import re
import sys
import threading
from contextlib import contextmanager
from dataclasses import dataclass, field
from functools import wraps
from typing import Dict, List, Optional, Set, Tuple, Union
from urllib.parse import urlsplit

from tribler.core.components.libtorrent.utils.libtorrent_helper import libtorrent as lt
from tribler.core.utilities.sentinels import sentinel

logger = logging.getLogger(__name__)

# Sentinel representing that SQLite must create database in-memory with ":memory:" argument
MEMORY_DB = sentinel('MEMORY_DB')
INT32_MAX = 2 ** 31 - 1

_switch_interval_lock = threading.Lock()


@contextmanager
def switch_interval(value):
    """ Temporarily change the sys.setswitchinterval value."""
    with _switch_interval_lock:
        previous_value = sys.getswitchinterval()
        sys.setswitchinterval(value)
        try:
            yield
        finally:
            sys.setswitchinterval(previous_value)


# Decorator to prevent creating new object properties at runtime.
# Copy-pasted from SO post: https://stackoverflow.com/a/29368642
# (c) Yoann Quenach de Quivillic
def froze_it(cls):
    cls.__frozen = False

    def frozensetattr(self, key, value):
        if self.__frozen and not hasattr(self, key):
            exc_text = "Class {} is frozen. Cannot set {} = {}".format(cls.__name__, key, value)
            raise AttributeError(exc_text)
        else:
            object.__setattr__(self, key, value)

    def init_decorator(func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            func(self, *args, **kwargs)
            self.__frozen = True

        return wrapper

    cls.__setattr__ = frozensetattr
    cls.__init__ = init_decorator(cls.__init__)

    return cls


def is_valid_url(url):
    """
    Checks whether the given URL is a valid URL.

    Both UDP and HTTP URLs will be validated correctly.

    :param url: an object representing the URL
    :return: Boolean specifying whether the URL is valid
    """
    if ' ' in url.strip():
        return
    if url.lower().startswith('udp'):
        url = url.lower().replace('udp', 'http', 1)
    split_url = urlsplit(url)

    return not (split_url[0] == '' or split_url[1] == '')


def parse_magnetlink(url: Union[str, bytes]) -> Tuple[str, bytes, List[str]]:
    """
    Parses the magnet link provided by the given URL.

    The output of this file consists of:
        -   name: The display name of the magnet link
        -   infohash: The URI containing the file hash of the magnet link
        -   trackers: The list of Tracker URLs

    The RuntimeError is raised when the magnet link is invalid.
    """
    params = lt.parse_magnet_uri(url)
    return params.name, params.info_hash.to_bytes(), params.trackers


def is_simple_match_query(query):
    """
    Check if the query is a simple match query with AND operators only.
    Supports unicode characters.
    """
    pattern = re.compile(r"\"[\\\w]+\"\*", flags=re.UNICODE)
    splits = pattern.split(query)
    for connector in splits:
        if connector and connector != " AND ":
            return False
    return True


def has_bep33_support():
    """
    Return whether our libtorrent version has support for BEP33 (DHT health lookups).
    Also see https://github.com/devos50/libtorrent/tree/bep33_support

    Previously, to check if BEP33 support is available was done by checking
    'dht_pkt_alert' in dir(lt)

    Currently for PyPi package of libtorrent, this is not sufficient to check full BEP33 support.
    This is because 'dht_pkt_alert' is exposed but it is currently not possible to send DHT scrape
    requests. This is documented in the following GitHub issue:
    Check progress here: https://github.com/arvidn/libtorrent/issues/3701

    So, for now, until the upstream issue on libtorrent is fixed,
    we disable BEP33 support by simply returning False here.
    """
    return False


def is_infohash(infohash):
    return infohash and len(infohash) == 40 and is_hex_string(infohash)


def is_channel_public_key(key):
    return key and len(key) == 128 and is_hex_string(key)


def is_hex_string(text):
    try:
        int(text, 16)
        return True
    except ValueError:
        return False


def bdecode_compat(packet_buffer: bytes) -> Optional[Dict]:
    """
    Utility method to make libtorrent bdecode() with Python3 in the existing Tribler codebase.
    We should change this when Libtorrent wrapper is refactored.
    """
    try:
        return lt.bdecode(packet_buffer)
    except RuntimeError:
        return None


def random_infohash(random_gen=None) -> bytes:
    r = random_gen or random
    return r.getrandbits(20 * 8).to_bytes(20, byteorder='big')


def is_frozen():
    """
    Return whether we are running in a frozen environment
    """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        sys._MEIPASS  # pylint: disable=protected-access
    except Exception:  # pylint: disable=broad-except
        return False
    return True


fts_query_re = re.compile(r'\w+', re.UNICODE)
tags_re = re.compile(r'#[^\s^#]{3,50}(?=[#\s]|$)')


@dataclass
class Query:
    original_query: str
    tags: Set[str] = field(default_factory=set)
    fts_text: str = ''


def parse_query(query: str) -> Query:
    """
    The query structure:
        query = [tag1][tag2] text
                 ^           ^
                tags        fts query
    """
    if not query:
        return Query(original_query=query)

    tags, remaining_text = extract_tags(query)
    return Query(original_query=query, tags=tags, fts_text=remaining_text.strip())


def extract_tags(text: str) -> Tuple[Set[str], str]:
    if not text:
        return set(), ''

    tags = set()
    positions = [0]

    for m in tags_re.finditer(text):
        tag = m.group(0)[1:]
        tags.add(tag.lower())
        positions.extend(itertools.chain.from_iterable(m.regs))
    positions.append(len(text))

    remaining_text = ''.join(text[positions[i]: positions[i + 1]] for i in range(0, len(positions) - 1, 2))
    return tags, remaining_text


def to_fts_query(text):
    if not text:
        return None

    words = [f'"{w}"' for w in fts_query_re.findall(text) if w]
    if not words:
        return None

    return ' '.join(words)


def parse_bool(obj):
    """
    Parse input to boolean True or False
    Allow parsing text 'false', 'true' '1', '0' to boolean

    :param obj: Object to parse
    """
    if isinstance(obj, str):
        if obj.lower() == "false":
            return False

        try:
            return bool(int(obj))
        except ValueError:
            pass
    return bool(obj)


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


def get_normally_distributed_number_with_zero_mean(upper_limit=100) -> float:
    """
    Returns a random floating point number based on normal distribution with mean set as zero.
    This favors the lower value numbers to be selected more than the higher value numbers.
    The returned number is below the upper_limit value provided.
    """
    mean = 0
    if upper_limit <= 1:
        return mean

    while True:
        result = random.normalvariate(mean, upper_limit / 3)
        if abs(result) < upper_limit:
            return result


def get_normally_distributed_positive_integer(upper_limit=100) -> int:
    return abs(int(get_normally_distributed_number_with_zero_mean(upper_limit=upper_limit)))


def get_normally_distributed_positive_integers(size=1, upper_limit=100) -> list:
    """
    Returns a list of non-repeated integer numbers based on normal distribution with mean value zero.
    """
    if size > upper_limit:
        raise ValueError("Cannot return more numbers than the upper limit")

    numbers = []
    while len(numbers) < size:
        number = get_normally_distributed_positive_integer(upper_limit=upper_limit)
        if number not in numbers:
            numbers.append(number)
    return numbers


def make_async_loop_fragile(loop):
    """Makes asyncio loop fragile. Should be used only for test purposes."""

    def fragile_exception_handler(_, context):
        try:
            raise context.get('exception')
        except BaseException:  # pylint: disable=broad-except
            logger.exception('Exception in the fragile except handler.', exc_info=True)
        os._exit(1)  # pylint: disable=protected-access

    loop.set_exception_handler(fragile_exception_handler)


def safe_repr(obj):
    try:
        return repr(obj)
    except Exception as e:  # pylint: disable=broad-except
        return f'<Repr of {object.__repr__(obj)} raises {e.__class__.__name__}: {e}>'
