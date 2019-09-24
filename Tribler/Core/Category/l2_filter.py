from __future__ import absolute_import

import os
import re
import sys

from Tribler.Core.Utilities.install_dir import get_lib_path


# !ACHTUNG! We must first read the line into a file, then release the lock, and only then pass it to regex compiler.
# Otherwise, there is an annoying race condition that reads in an empty file!
if sys.version_info.major > 2:
    with open(os.path.join(get_lib_path(), 'Core', 'Category', 'level2.regex'), encoding="utf-8") as f:
        regex = f.read().strip()
        stoplist_expression = re.compile(regex, re.IGNORECASE)
else:
    with open(os.path.join(get_lib_path(), 'Core', 'Category', 'level2.regex')) as f:
        regex = f.read().decode("utf-8").strip()
        stoplist_expression = re.compile(regex, re.IGNORECASE)


def is_forbidden(txt):
    return bool(stoplist_expression.search(txt))
