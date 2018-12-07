"""
This file contains various utility methods.
"""
from __future__ import absolute_import

import sys

if sys.version_info.major > 2:
    cast_to_unicode_utf8 = lambda x: "".join([chr(c) for c in x]) if isinstance(x, bytes) else str(x)
else:
    cast_to_unicode_utf8 = lambda x: x.decode('utf-8')
