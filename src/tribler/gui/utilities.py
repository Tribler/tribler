import hashlib
import inspect
import json
import logging
import math
import os
import sys
import time
import traceback
import types
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable, Dict, List, Optional
from urllib.parse import quote_plus
from uuid import uuid4

from PyQt5.QtCore import (
    QCoreApplication,
    QLocale,
    QPoint,
    QSettings,
    QTranslator,
    pyqtSignal,
)
from PyQt5.QtGui import QPixmap, QRegion
from PyQt5.QtNetwork import QNetworkReply
from PyQt5.QtWidgets import QApplication, QMessageBox

import tribler.gui
from tribler.core.components.database.db.layers.knowledge_data_access_layer import ResourceType
from tribler.gui.defs import CORRUPTED_DB_WAS_FIXED_MESSAGE, HEALTH_DEAD, HEALTH_GOOD, HEALTH_MOOT, HEALTH_UNCHECKED

# fmt: off

logger = logging.getLogger(__name__)

NUM_VOTES_BARS = 8
I18N_DIR = "i18n"
LANGUAGES_FILE = "languages.json"


class TranslatedString(str):
    """ This class is used to wrap translated strings to be able to log untranslated strings in case of errors.
        Thanks to this class no `KeyError` exceptions are raised when a translation is missing.
    """

    def __new__(cls, translation, original_string):  # pylint: disable=unused-argument
        return super().__new__(cls, translation)

    def __init__(self, translation: str, original_string: str):  # pylint: disable=unused-argument
        super().__init__()
        self.original_string = original_string

    def __mod__(self, other):
        try:
            return str.__mod__(self, other)
        except KeyError as e:
            msg = f'No value provided for {e} in translation "{self}", original string: "{self.original_string}"'
            logger.warning(f'{type(e).__name__}: {msg}')
            return self.original_string % other
        except TypeError as e:
            msg = f'Wrong number of parameters in translation "{self}", original string: "{self.original_string}"'
            logger.warning(f'{type(e).__name__}: {msg}')
            return self.original_string % other


def tr(key):
    translated_string = QCoreApplication.translate('@default', key)
    return TranslatedString(translated_string, original_string=key)


VOTES_RATING_DESCRIPTIONS = (
    tr("Zero popularity"),
    tr("Very low popularity"),
    tr("3rd tier popularity"),
    tr("2nd tier popularity"),
    tr("1st tier popularity"),
)


def data_item2uri(data_item):
    return f"magnet:?xt=urn:btih:{data_item['infohash']}&dn={data_item['name']}"


def index2uri(index):
    return data_item2uri(index.model().data_items[index.row()])


def format_size(num, suffix='B', precision=1):
    for unit in ['', 'k', 'M', 'G', 'T', 'P', 'E', 'Z']:
        if abs(num) < 1024.0:
            return f"{num:3.{precision}f} {unit}{suffix}"
        num /= 1024.0
    return f"{num:.1f} Yi{suffix}"


def format_speed(num):
    return f"{format_size(num)}/s"


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

    data = {'years': years, 'weeks': weeks, 'days': days, 'hours': hours, 'minutes': minutes, 'seconds': seconds}

    if years >= 100:
        return tr("Forever")
    if years > 0:
        return tr("%(years)iy %(weeks)iw") % data
    if weeks > 0:
        return tr("%(weeks)iw %(days)id") % data
    if days > 0:
        return tr("%(days)id %(hours)ih") % data
    if hours > 0:
        return tr("%(hours)ih %(minutes)im") % data
    if minutes > 0:
        return tr("%(minutes)im %(seconds)is") % data
    return tr("%(seconds)is") % data


def get_base_path():
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.dirname(tribler.gui.__file__)
    return base_path


TRANSLATIONS_DIR = os.path.join(get_base_path(), "i18n")


def get_available_translations():
    # Returns a list of tuples: (lanugage_name, language_code) for each available translation
    translations_list = [str(p.stem) for p in Path(TRANSLATIONS_DIR).glob('*.qm')]
    translations_list.append("en_US")

    result = {}
    for lang_code in translations_list:
        loc = QLocale(lang_code)
        lang_name = loc.languageToString(loc.language())
        result[lang_name] = lang_code
    return result


AVAILABLE_TRANSLATIONS = get_available_translations()


def get_ui_file_path(filename):
    return os.path.join(get_base_path(), 'qt_resources', filename)


def get_i18n_file_path(filename):
    return Path(get_base_path()) / I18N_DIR / filename


def get_languages_file_content():
    languages_path = get_i18n_file_path(LANGUAGES_FILE)
    content = Path(languages_path).read_text(encoding='utf-8')
    return json.loads(content)


def get_image_path(filename: str, convert_slashes_to_forward: bool = False) -> str:
    """
    Return a path to a particular file in the image directory.

    If convert_slashes_to_forward is set to True, backward slashes are converted to forward slashes.
    This can be used to ensure that images on Windows can be correctly loaded.
    Also see https://stackoverflow.com/questions/26121737/qt-stylesheet-background-image-from-filepath.
    """
    path = os.path.join(get_base_path(), 'images', filename)
    if convert_slashes_to_forward:
        path = path.replace("\\", "/")
    return path


def get_font_path(filename: str) -> str:
    """
    Return a path to a particular font in the fonts directory.
    """
    return os.path.join(get_base_path(), 'fonts', filename)


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


def create_api_key() -> str:
    return os.urandom(16).hex()


def format_api_key(api_key) -> str:
    if isinstance(api_key, bytes):
        # In Tribler application, api_key is stored as a string. But in gui_settings api_key is stored as bytes,
        # for compatibility with previous versions of Tribler. Otherwise, a user can get an error if he rolls back
        # to a previous version of Tribler, that cannot read str values of api_key from GUI settings.
        return api_key.decode('ascii')

    if isinstance(api_key, str):
        # If we read api_keys from gui_settings as str, we need to save it as bytes, to restore
        # settings compatibility with previous versions of Tribler
        return api_key

    raise ValueError(
        f'Got unexpected value type of api_key from gui settings ' f'(should be str or bytes): {type(api_key).__name__}'
    )


def set_api_key(gui_settings: QSettings, api_key: str):
    api_key_bytes = api_key.encode('ascii')
    gui_settings.setValue("api_key", api_key_bytes)


def is_dir_writable(path):
    """
    Checks if the directory is writable. Creates the directory if one does not exist.
    :param path: absolute path of directory
    :return: True if writable, False otherwise
    """

    directory = Path(path)
    random_file = directory / f'tribler_temp_delete_me_{uuid4()}'
    try:
        directory.mkdir(parents=True, exist_ok=True)
        random_file.open('w')
        random_file.unlink()
    except (OSError, UnicodeEncodeError) as e:
        return False, e
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
    magnet = f"magnet:?xt=urn:btih:{infohash}"
    if name:
        magnet = f"{magnet}&dn={quote_plus_unicode(name)}"
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
    return f"  {'┃' * votes_count(votes)} "


def format_votes_rich_text(votes=0.0):
    votes_count_full = votes_count(votes)
    votes_count_empty = votes_count(1.0) - votes_count_full

    rating_rich_text = (
            f"<font color=#BBBBBB>{'┃' * votes_count_full}</font>" +
            f"<font color=#444444>{'┃' * votes_count_empty}</font>"
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

    # Step 2: construct a lightweight StackSummary object which does not contain
    # actual frames or locals, to avoid memory leak
    try:
        summary = traceback.StackSummary.extract(traceback.walk_tb(source), capture_locals=False)
    finally:
        del source

    # Step 3: Wrap the ``callback`` and inject our creation stack if an error occurs.
    #         The BaseException instead of Exception is intentional: this makes sure interrupts of infinite loops show
    #         the source callback stack for debugging.
    def trackback_wrapper(*args, **kwargs):
        try:
            callback(*args, **kwargs)
        except BaseException as exc:
            traceback_str = '\n' + ''.join(summary.format())
            raise exc from CreationTraceback(traceback_str)

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


def dict_item_is_any_of(d, key, values):
    if not d or not key or not values:
        return False
    return key in d and d[key] in values


def get_translator(language=None):
    system_locale = QLocale.system()
    # Remapping the language from uiLanguages is a workaround for an annoying bug in Qt,
    # which makes QTranslator use the system language (e.g. the language the OS was installed in),
    # instead of the user-display language the user installed later.
    locale = QLocale(language) if language is not None else QLocale(system_locale.uiLanguages()[0])
    logger.info("Available Tribler translations %s", AVAILABLE_TRANSLATIONS)
    logger.info("System language: %s, Tribler language: %s", system_locale.uiLanguages(), locale.uiLanguages())
    translator = QTranslator()
    filename = ""
    translator.load(locale, filename, directory=TRANSLATIONS_DIR)
    return translator


def take_screenshot(window, screenshots_dir):
    timestamp = int(time.time())
    pixmap = QPixmap(window.rect().size())
    window.render(pixmap, QPoint(), QRegion(window.rect()))
    screenshots_dir.mkdir(exist_ok=True)
    img_name = 'exception_screenshot_%d.jpg' % timestamp
    pixmap.save(str(screenshots_dir / img_name))


def show_message_box(text: str = '', title: str = 'Error', icon: QMessageBox.Icon = QMessageBox.Critical):
    message_box = QMessageBox()
    message_box.setIcon(icon)
    message_box.setStandardButtons(QMessageBox.Yes)
    message_box.setWindowTitle(title)
    message_box.setText(text)
    message_box.exec_()


def show_message_corrupted_database_was_fixed(db_path: Optional[str] = None):
    text = tr(CORRUPTED_DB_WAS_FIXED_MESSAGE)
    if db_path:
        text = f'{text}:\n\n{db_path}'

    message_box = QMessageBox(icon=QMessageBox.Critical, text=text)
    message_box.setWindowTitle(tr("Database corruption detected"))
    message_box.exec()


def make_network_errors_dict() -> Dict[int, str]:
    network_errors = {}
    for name in dir(QNetworkReply):
        if name.endswith('Error'):
            value = getattr(QNetworkReply, name)
            if isinstance(value, int):
                network_errors[value] = name
    return network_errors


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


def get_objects_with_predicate(data_item: Dict, predicate: ResourceType) -> List[str]:
    """
    Extract the objects that have a particular predicate from a particular data item.
    """
    return [stmt["object"] for stmt in data_item.get("statements", ()) if stmt["predicate"] == predicate]
