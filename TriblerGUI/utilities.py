from datetime import datetime
import hashlib
import heapq
from itertools import izip, count
from operator import itemgetter
import os
import re
import sys

import TriblerGUI
from TriblerGUI.defs import VIDEO_EXTS


def format_size(num, suffix='B'):
    for unit in ['','k','M','G','T','P','E','Z']:
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


def timestamp_to_time(timestamp):
    today = datetime.today()
    discovered = datetime.fromtimestamp(timestamp)

    diff = today - discovered
    if diff.days > 0 or today.day != discovered.day:
        return discovered.strftime('%d-%m-%Y')
    return discovered.strftime('Today %H:%M')


def get_color(name):
    """
    This method deterministically determines a color of a given name. This is done by taking the MD5 hash of the text.
    """
    md5_hash = hashlib.md5()
    md5_hash.update(name.encode('utf-8'))
    md5_str_hash = md5_hash.hexdigest()

    red = int(md5_str_hash[0:10], 16) % 128 + 127
    green = int(md5_str_hash[10:20], 16) % 128 + 127
    blue = int(md5_str_hash[20:30], 16) % 128 + 127

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
    from datetime import datetime
    now = datetime.now()
    if type(time) is int:
        diff = now - datetime.fromtimestamp(time)
    elif isinstance(time,datetime):
        diff = now - time
    elif not time:
        diff = now - now
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


def get_ui_file_path(filename):
    return os.path.join(get_base_path(), 'qt_resources/%s' % filename)


def get_image_path(filename):
    return os.path.join(get_base_path(), 'images/%s' % filename)
