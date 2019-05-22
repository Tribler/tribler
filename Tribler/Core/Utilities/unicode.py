"""
Conversions to unicode.

Author(s): Arno Bakker
"""
from __future__ import absolute_import

import sys

import chardet

from six import binary_type, text_type


def ensure_unicode(s, encoding, errors='strict'):
    """Similar to six.ensure_text() except that the encoding parameter is *not* optional
    """
    if isinstance(s, binary_type):
        return s.decode(encoding, errors)
    elif isinstance(s, text_type):
        return s
    else:
        raise TypeError("not expecting type '%s'" % type(s))


def ensure_unicode_detect_encoding(s):
    """Similar to ensure_unicode() but use chardet to detect the encoding
    """
    if isinstance(s, binary_type):
        try:
            return s.decode('utf-8')  # Try converting bytes --> Unicode utf-8
        except UnicodeDecodeError:
            charenc = chardet.detect(s)['encoding']
            return s.decode(charenc) if charenc else s  # Hope for the best
    elif isinstance(s, text_type):
        return s
    else:
        raise TypeError("not expecting type '%s'" % type(s))


def recursive_unicode(obj):
    """
    Converts any bytes within a data structure to unicode strings. Bytes are assumed to be UTF-8 encoded text.
    :param obj: object comprised of lists/dicts/strings/bytes
    :return: obj: object comprised of lists/dicts/strings
    """
    if isinstance(obj, dict):
        return {recursive_unicode(k):recursive_unicode(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [recursive_unicode(i) for i in obj]
    elif isinstance(obj, binary_type):
        return obj.decode('utf8')
    return obj


def recursive_bytes(obj):
    """
    Converts any unicode strings within a Python data structure to bytes. Strings will be encoded using UTF-8.
    :param obj: object comprised of lists/dicts/strings/bytes
    :return: obj: object comprised of lists/dicts/bytes
    """
    if isinstance(obj, dict):
        return {recursive_bytes(k):recursive_bytes(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [recursive_bytes(i) for i in obj]
    elif isinstance(obj, text_type):
        return obj.encode('utf8')
    return obj
