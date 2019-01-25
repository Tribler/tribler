from __future__ import absolute_import

from binascii import hexlify

"""
This file contains some utility methods that are used by the API.
"""

from six import string_types
from six.moves import xrange

from twisted.web import http

import Tribler.Core.Utilities.json_util as json


def return_handled_exception(request, exception):
    """
    :param request: the request that encountered the exception
    :param exception: the handled exception
    :return: JSON dictionary describing the exception
    """
    request.setResponseCode(http.INTERNAL_SERVER_ERROR)
    return json.dumps({
        u"error": {
            u"handled": True,
            u"code": exception.__class__.__name__,
            u"message": exception.message
        }
    })


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
    This is required since Dispersy members might add invalid characters to their strings and we are unable to utf8
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
        elif isinstance(value, string_types):
            new_dict[key] = value.decode('utf-8', 'ignore')
        else:
            new_dict[key] = value

    return new_dict


def fix_unicode_array(arr):
    """
    Iterate over the items of the array and remove invalid unicode characters.
    """
    new_arr = []

    for ind in xrange(len(arr)):
        if isinstance(arr[ind], string_types):
            new_arr.append(arr[ind].decode('utf-8', 'ignore'))
        elif isinstance(arr[ind], dict):
            new_arr.append(fix_unicode_dict(arr[ind]))
        else:
            new_arr.append(arr[ind])

    return new_arr
