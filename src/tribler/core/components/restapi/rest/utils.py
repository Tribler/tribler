"""
This file contains some utility methods that are used by the API.
"""
import linecache
import sys
import threading
from types import FrameType
from typing import Dict, Iterator, List, Optional

from tribler.core.components.restapi.rest.rest_endpoint import HTTP_INTERNAL_SERVER_ERROR, RESTResponse
from tribler.core.utilities.utilities import switch_interval

ONE_SECOND = 1


def return_handled_exception(request, exception):
    """
    :param request: the request that encountered the exception
    :param exception: the handled exception
    :return: JSON dictionary describing the exception
    """
    return RESTResponse({
        "error": {
            "handled": True,
            "code": exception.__class__.__name__,
            "message": str(exception)
        }
    }, status=HTTP_INTERNAL_SERVER_ERROR)


def get_parameter(parameters, name):
    """
    Return a specific parameter with a name from a HTTP request (or None if that parameter is not available).
    """
    if name not in parameters or len(parameters[name]) == 0:
        return None
    return parameters[name][0]


def fix_unicode_dict(d):
    """
    This method removes illegal (unicode) characters recursively from a dictionary.
    This is required since IPv8 peers might add invalid characters to their strings and we are unable to utf8
    encode these when sending the data over the API.
    """
    new_dict = {}

    for key, value in d.items():
        if isinstance(value, dict):
            new_dict[key] = fix_unicode_dict(value)
        elif isinstance(value, tuple):
            new_dict[key] = fix_unicode_array(list(value))
        elif isinstance(value, list):
            new_dict[key] = fix_unicode_array(value)
        elif isinstance(value, bytes):
            new_dict[key] = value.decode('utf-8', 'ignore')
        else:
            new_dict[key] = value

    return new_dict


def fix_unicode_array(arr):
    """
    Iterate over the items of the array and remove invalid unicode characters.
    """
    new_arr = []

    for item in arr:
        if isinstance(item, bytes):
            new_arr.append(item.decode('utf-8', 'ignore'))
        elif isinstance(item, dict):
            new_arr.append(fix_unicode_dict(item))
        else:
            new_arr.append(item)

    return new_arr


def shorten(s: Optional[str], width: int = 50, placeholder='[...]', cut_at_the_end: bool = True):
    """ Shorten a string to a given width.
        Example: shorten('hello world', 5) -> 'hello[...]'
    """
    if s and len(s) > width:
        return f'{s[:width]}{placeholder}' if cut_at_the_end else f'{placeholder}{s[len(s) - width:]}'
    return s


def _format_frames(frame: Optional[FrameType], file_width: int = 50, value_width: int = 100) -> Iterator[str]:
    """ Format a stack trace."""
    while frame:
        filename = shorten(frame.f_code.co_filename, width=file_width, cut_at_the_end=False)
        header = f"{filename}:, line {frame.f_lineno}, in {frame.f_code.co_name}"
        source_line = linecache.getline(frame.f_code.co_filename, frame.f_lineno).strip() or "<source is unknown>"
        local = ''
        for key, value in list(frame.f_locals.items()):
            try:
                value = repr(value)
            except Exception as e:  # pylint: disable=broad-except
                value = f'<exception when taking repr: {e.__class__.__name__}: {e}>'
            value = shorten(value, width=value_width)
            local += f'\t{key} = {value}\n'
        frame = frame.f_back
        yield f'{header}\n' \
              f'    {source_line}\n' \
              f'{local}'


def get_threads_info() -> List[Dict]:
    """
    Return information about available threads.
    """

    result = []
    with switch_interval(ONE_SECOND):
        for t in threading.enumerate():
            frame = sys._current_frames().get(t.ident, None)  # pylint: disable=protected-access

            result.append({
                'thread_id': t.ident,
                'thread_name': t.name,
                'frames': list(_format_frames(frame)),
            })
    return result
