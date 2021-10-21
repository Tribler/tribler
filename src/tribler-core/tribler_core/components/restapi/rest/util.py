"""
This file contains some utility methods that are used by the API.
"""
from tribler_core.components.restapi.rest.rest_endpoint import HTTP_INTERNAL_SERVER_ERROR, RESTResponse


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
