"""
Conversions to unicode.

Author(s): Arno Bakker
"""
from __future__ import absolute_import

import sys

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
