import hashlib
import os
import re
import sys
from datetime import datetime, timedelta
from urllib import quote_plus

import TriblerGUI
from TriblerGUI.defs import VIDEO_EXTS


def format_size(num, suffix='B'):
    for unit in ['', 'k', 'M', 'G', 'T', 'P', 'E', 'Z']:
        if abs(num) < 1024.0:
            return "%3.1f %s%s" % (num, unit, suffix)
        num /= 1024.0
    return "%.1f %s%s" % (num, 'Yi', suffix)


def format_speed(num):
    return "%s/s" % format_size(num)


def seconds_to_string(seconds):
    minutes = seconds / 60
    seconds_left = seconds % 60
    return "%d:%02d" % (minutes, seconds_left)


def seconds_to_hhmm_string(seconds):
    hours = int(seconds) / 3600
    seconds -= hours * 3600
    return "%d:%02d" % (hours, seconds / 60)


def string_to_seconds(time_str):
    parts = time_str.split(":")
    if len(parts) != 2:
        raise ValueError("Invalid time string")

    hours = float(parts[0])
    minutes = float(parts[1])
    return hours * 3600 + minutes * 60


def timestamp_to_time(timestamp):
    today = datetime.today()
    discovered = datetime.fromtimestamp(timestamp)

    diff = today - discovered
    if diff.days > 0 or today.day != discovered.day:
        return discovered.strftime('%d-%m-%Y %H:%M')
    return discovered.strftime('Today %H:%M')


def get_color(name):
    """
    This method deterministically determines a color of a given name. This is done by taking the MD5 hash of the text.
    """
    md5_hash = hashlib.md5()
    md5_hash.update(name.encode('utf-8'))
    md5_str_hash = md5_hash.hexdigest()

    red = int(md5_str_hash[0:10], 16) % 128 + 100
    green = int(md5_str_hash[10:20], 16) % 128 + 100
    blue = int(md5_str_hash[20:30], 16) % 128 + 100

    return '#%02x%02x%02x' % (red, green, blue)


def is_video_file(filename):
    _, ext = os.path.splitext(filename)
    if ext.startswith('.'):
        ext = ext[1:]
    return ext in VIDEO_EXTS


def pretty_date(time=False):
    """
    Get a datetime object or a int() Epoch timestamp and return a
    pretty string like 'an hour ago', 'Yesterday', '3 months ago',
    'just now', etc
    """
    now = datetime.now()
    if isinstance(time, int):
        diff = now - datetime.fromtimestamp(time)
    elif isinstance(time, datetime):
        diff = now - time
    elif not time:
        diff = timedelta(0)
    second_diff = diff.seconds
    day_diff = diff.days

    if day_diff < 0:
        return ''

    if day_diff == 0:
        if second_diff < 10:
            return "just now"
        if second_diff < 60:
            return str(second_diff) + " seconds ago"
        if second_diff < 120:
            return "a minute ago"
        if second_diff < 3600:
            return str(second_diff / 60) + " minutes ago"
        if second_diff < 7200:
            return "an hour ago"
        if second_diff < 86400:
            return str(second_diff / 3600) + " hours ago"
    if day_diff == 1:
        return "yesterday"
    if day_diff < 7:
        return str(day_diff) + " days ago"
    if day_diff < 31:
        return str(day_diff / 7) + " weeks ago"
    if day_diff < 365:
        return str(day_diff / 30) + " months ago"
    return str(day_diff / 365) + " years ago"


def duration_to_string(seconds):
    weeks = int(seconds / (60 * 60 * 24 * 7))
    seconds -= weeks * (60 * 60 * 24 * 7)
    days = int(seconds / (60 * 60 * 24))
    seconds -= days * (60 * 60 * 24)
    hours = int(seconds / (60 * 60))
    seconds -= hours * (60 * 60)
    minutes = int(seconds / 60)
    seconds -= minutes * 60
    seconds = int(seconds)

    if weeks > 0:
        return "{}w {}d".format(weeks, days)
    if days > 0:
        return "{}d {}h".format(days, hours)
    if hours > 0:
        return "{}h {}m".format(hours, minutes)
    if minutes > 0:
        return "{}m {}s".format(minutes, seconds)
    return "{}s".format(seconds)


def split_into_keywords(query):
    RE_KEYWORD_SPLIT = re.compile(r"[\W_]", re.UNICODE)
    return [kw for kw in RE_KEYWORD_SPLIT.split(query.lower()) if len(kw) > 0]


def get_base_path():
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.dirname(TriblerGUI.__file__)
    return base_path


def is_frozen():
    """
    Return whether we are running in a frozen environment
    """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        _ = sys._MEIPASS
    except Exception:
        return False
    return True


def get_ui_file_path(filename):
    return os.path.join(get_base_path(), 'qt_resources/%s' % filename)


def get_image_path(filename):
    return os.path.join(get_base_path(), 'images/%s' % filename)


def bisect_right(item, item_list, is_torrent):
    """
    This method inserts a channel/torrent in a sorted list. The sorting is based on relevance score.
    The implementation is based on bisect_right.
    """
    lo = 0
    hi = len(item_list)
    while lo < hi:
        mid = (lo+hi) // 2
        if item['relevance_score'] == item_list[mid]['relevance_score'] and is_torrent:
            if len(split_into_keywords(item['name'])) < len(split_into_keywords(item_list[mid]['name'])):
                hi = mid
            else:
                lo = mid + 1
        elif item['relevance_score'] > item_list[mid]['relevance_score']:
            hi = mid
        else:
            lo = mid + 1
    return lo


def get_gui_setting(gui_settings, value, default, is_bool=False):
    """
    Utility method to get a specific GUI setting. The is_bool flag defines whether we expect a boolean so we convert it
    since on Windows, all values are saved as plain text.
    """
    val = gui_settings.value(value, default)
    if is_bool:
        val = val == True or val == 'true'
    return val


def is_dir_writable(path):
    """
    Checks if the directory is writable. Creates the directory if one does not exist.
    :param path: absolute path of directory
    :return: True if writable, False otherwise
    """
    try:
        if not os.path.exists(path):
            os.makedirs(path)
        open(os.path.join(path, 'temp'), 'w')
    except IOError as io_error:
        return False, io_error
    except OSError as os_error:
        return False, os_error
    else:
        os.remove(os.path.join(path, 'temp'))
        return True, None


def unicode_quoter(c):
    """
    Quote a single unicode character for URI form.

    :param c: the character to quote
    :return: the safe URI string
    """
    try:
        return quote_plus(c)
    except KeyError:
        return c


def quote_plus_unicode(s):
    """
    Quote a unicode string for URI form.

    :param s: the string to quote
    :return: the safe URI string
    """
    return ''.join([unicode_quoter(c) for c in s])


def prec_div(number, precision):
    """
    Divide a given number by 10^precision.
    """
    return float(number) / float(10 ** precision)
