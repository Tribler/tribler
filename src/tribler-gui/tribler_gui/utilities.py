import hashlib
import inspect
import logging
import math
import os
import re
import sys
import types
from datetime import datetime, timedelta
from typing import Callable
from urllib.parse import quote_plus
from uuid import uuid4

from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import QApplication

import tribler_gui
from tribler_gui.defs import HEALTH_DEAD, HEALTH_GOOD, HEALTH_MOOT, HEALTH_UNCHECKED, VIDEO_EXTS
from tribler_gui.i18n import tr

NUM_VOTES_BARS = 8

VOTES_RATING_DESCRIPTIONS = (
    "Zero popularity",
    "Very low popularity",
    "3rd tier popularity",
    "2nd tier popularity",
    "1st tier popularity",
)


def data_item2uri(data_item):
    return f"magnet:?xt=urn:btih:{data_item[u'infohash']}&dn={data_item[u'name']}"


def index2uri(index):
    return data_item2uri(index.model().data_items[index.row()])


def format_size(num, suffix='B'):
    for unit in ['', 'k', 'M', 'G', 'T', 'P', 'E', 'Z']:
        if abs(num) < 1024.0:
            return f"{num:3.1f} {unit}{suffix}"
        num /= 1024.0
    return "{:.1f} {}{}".format(num, 'Yi', suffix)


def format_speed(num):
    return "%s/s" % format_size(num)


def seconds_to_string(seconds):
    minutes = seconds // 60
    seconds_left = seconds % 60
    return "%d:%02d" % (minutes, seconds_left)


def seconds_to_hhmm_string(seconds):
    hours = int(seconds) // 3600
    seconds -= hours * 3600
    return "%d:%02d" % (hours, seconds // 60)


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

    return f'#{red:02x}{green:02x}{blue:02x}'


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
        try:
            diff = now - datetime.fromtimestamp(time)
        except ValueError:  # The time passed is out of range - return an empty string
            return ''
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
            return tr("just now")
        if second_diff < 60:
            return str(second_diff) + tr(" seconds ago")
        if second_diff < 120:
            return tr("a minute ago")
        if second_diff < 3600:
            return str(second_diff // 60) + tr(" minutes ago")
        if second_diff < 7200:
            return tr("an hour ago")
        if second_diff < 86400:
            return str(second_diff // 3600) + tr(" hours ago")
    if day_diff == 1:
        return tr("yesterday")
    if day_diff < 7:
        return str(day_diff) + tr(" days ago")
    if day_diff < 31:
        weeks = day_diff // 7
        word = tr("week") if weeks == 1 else tr("weeks")
        return str(weeks) + " " + word + tr(" ago")
    if day_diff < 365:
        months = day_diff // 30
        word = tr("month") if months == 1 else tr("months")
        return str(months) + " " + word + tr(" ago")

    years = day_diff // 365
    word = tr("year") if years == 1 else tr("years")
    return str(years) + " " + word + tr(" ago")


def duration_to_string(seconds):
    years = int(seconds // (60 * 60 * 24 * 365.249))
    seconds -= years * (60 * 60 * 24 * 365.249)
    weeks = int(seconds // (60 * 60 * 24 * 7))
    seconds -= weeks * (60 * 60 * 24 * 7)
    days = int(seconds // (60 * 60 * 24))
    seconds -= days * (60 * 60 * 24)
    hours = int(seconds // (60 * 60))
    seconds -= hours * (60 * 60)
    minutes = int(seconds // 60)
    seconds -= minutes * 60
    seconds = int(seconds)

    if years >= 100:
        return "Forever"
    if years > 0:
        return f"{years}y {weeks}w"
    if weeks > 0:
        return f"{weeks}w {days}d"
    if days > 0:
        return f"{days}d {hours}h"
    if hours > 0:
        return f"{hours}h {minutes}m"
    if minutes > 0:
        return f"{minutes}m {seconds}s"
    return f"{seconds}s"


def split_into_keywords(query):
    RE_KEYWORD_SPLIT = re.compile(r"[\W_]", re.UNICODE)
    return [kw for kw in RE_KEYWORD_SPLIT.split(query.lower()) if len(kw) > 0]


def get_base_path():
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.dirname(tribler_gui.__file__)
    return base_path


def get_ui_file_path(filename):
    return os.path.join(get_base_path(), 'qt_resources', filename)


def get_image_path(filename):
    return os.path.join(get_base_path(), 'images', filename)


def get_gui_setting(gui_settings, value, default, is_bool=False):
    """
    Utility method to get a specific GUI setting. The is_bool flag defines whether we expect a boolean so we convert it
    since on Windows, all values are saved as plain text.
    """
    try:
        val = gui_settings.value(value, default)
    except TypeError:
        val = default
    if is_bool:
        val = val == True or val == 'true'
    return val


def is_dir_writable(path):
    """
    Checks if the directory is writable. Creates the directory if one does not exist.
    :param path: absolute path of directory
    :return: True if writable, False otherwise
    """

    random_name = "tribler_temp_delete_me_" + str(uuid4())
    try:
        if not os.path.exists(path):
            os.makedirs(path)
        open(os.path.join(path, random_name), 'w')
        os.remove(os.path.join(path, random_name))
    except OSError as os_error:
        return False, os_error
    else:
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


def get_health(seeders, leechers, last_tracker_check):
    if last_tracker_check == 0:
        return HEALTH_UNCHECKED
    if seeders > 0:
        return HEALTH_GOOD
    elif leechers > 0:
        return HEALTH_MOOT
    else:
        return HEALTH_DEAD


def compose_magnetlink(infohash, name=None, trackers=None):
    """
    Composes magnet link from infohash, display name and trackers. The format is:
        magnet:?xt=urn:btih:<infohash>&dn=<name>[&tr=<tracker>]
    There could be multiple trackers so 'tr' field could be repeated.
    :param infohash: Infohash
    :param name: Display name
    :param trackers: Trackers
    :return: Magnet link
    """
    if not infohash:
        return ''
    magnet = "magnet:?xt=urn:btih:%s" % infohash
    if name:
        magnet = "{}&dn={}".format(magnet, quote_plus_unicode(name))
    if trackers and isinstance(trackers, list):
        for tracker in trackers:
            magnet = f"{magnet}&tr={tracker}"
    return magnet


def copy_to_clipboard(message):
    cb = QApplication.clipboard()
    cb.clear(mode=cb.Clipboard)
    cb.setText(message, mode=cb.Clipboard)


def html_label(text, background="#e4e4e4", color="#222222", bold=True):
    style = "background-color:" + background if background else ''
    style = style + ";color:" + color if color else style
    style = style + ";font-weight:bold" if bold else style
    return f"<label style='{style}'>&nbsp;{text}&nbsp;</label>"


def get_checkbox_style(color="#B5B5B5"):
    return (
        """QCheckBox { color: %s; }
                QCheckBox::indicator:unchecked {border: 1px solid #555;}
                """
        % color
    )


def votes_count(votes=0.0):
    votes = float(votes)
    # FIXME: this is a temp fix to cap the normalized value to 1.
    #  The votes should already be normalized before formatting it.
    votes = max(0.0, min(votes, 1.0))
    # We add sqrt to flatten the votes curve a bit
    votes = math.sqrt(votes)
    votes = int(math.ceil(votes * NUM_VOTES_BARS))
    return votes


def format_votes(votes=0.0):
    return "  %s " % ("┃" * votes_count(votes))


def format_votes_rich_text(votes=0.0):
    votes_count_full = votes_count(votes)
    votes_count_empty = votes_count(1.0) - votes_count_full

    rating_rich_text = (
        f"<font color=#BBBBBB>{'┃' * votes_count_full}</font>" + f"<font color=#444444>{'┃' * votes_count_empty}</font>"
    )
    return rating_rich_text


def get_votes_rating_description(votes=0.0):
    return VOTES_RATING_DESCRIPTIONS[math.ceil(float(votes_count(votes)) / 2)]


def connect(signal: pyqtSignal, callback: Callable):
    """
    By default calling ``signal.connect(callback)`` will dispose of context information.

    Practically, this leads to single line tracebacks when ``signal.emit()`` is invoked.
    This is very hard to debug.

    This function wraps the ``connect()`` call to give you additional traceback information, if the callback does crash.

    :param signal: the signal to ``connect()`` to.
    :param callback: the callback to connect (will be called after ``signal.emit(...)``.
    """

    # Step 1: At time of calling this function: get the stack frames.
    #         We reconstruct the stack as a ``traceback`` object.
    source = None
    for frame in list(inspect.stack())[1:]:
        source = types.TracebackType(source, frame.frame, frame.index or 0, frame.lineno)

    # Step 2: Wrap the ``callback`` and inject our creation stack if an error occurs.
    #         The BaseException instead of Exception is intentional: this makes sure interrupts of infinite loops show
    #         the source callback stack for debugging.
    def trackback_wrapper(*args, **kwargs):
        try:
            callback(*args, **kwargs)
        except BaseException as exc:
            source_exc = CreationTraceback().with_traceback(source)
            raise exc from source_exc

    try:
        setattr(callback, "tb_wrapper", trackback_wrapper)
    except AttributeError:
        # This is not a free function, but either an external library or a method bound to an instance.
        if not hasattr(callback, "tb_wrapper") and hasattr(callback, "__self__") and hasattr(callback, "__func__"):
            # methods are finicky: you can't set attributes on them.
            # Instead, we inject the handlers for each method in a dictionary on the instance.
            bound_obj = callback.__self__
            if not hasattr(bound_obj, "tb_mapping"):
                setattr(bound_obj, "tb_mapping", {})
            bound_obj.tb_mapping[callback.__func__.__name__] = trackback_wrapper
        else:
            logging.warning(
                "Unable to hook up connect() info to %s. Probably a 'builtin_function_or_method'.", repr(callback)
            )

    # Step 3: Connect our wrapper to the signal.
    signal.connect(trackback_wrapper)


def disconnect(signal: pyqtSignal, callback: Callable):
    """
    After using ``connect()`` to link a signal, use this function to disconnect from the given signal.

    This function will also work if the ``callback`` was connected directly with ``signal.connect()``.

    :param signal: the signal to ``disconnect()`` from.
    :param callback: the callback to connect (will be called after ``signal.emit(...)``.
    """
    if hasattr(callback, 'tb_wrapper'):
        disconnectable = callback.tb_wrapper
    elif hasattr(callback, "__self__") and hasattr(callback, "__func__"):
        disconnectable = callback.__self__.tb_mapping[callback.__func__.__name__]
    else:
        disconnectable = callback
    signal.disconnect(disconnectable)


class CreationTraceback(Exception):
    pass
