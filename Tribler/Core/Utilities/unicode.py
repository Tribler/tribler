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
