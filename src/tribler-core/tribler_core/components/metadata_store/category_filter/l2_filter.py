import re

from tribler_core.utilities.install_dir import get_lib_path

# !ACHTUNG! We must first read the line into a file, then release the lock, and only then pass it to regex compiler.
# Otherwise, there is an annoying race condition that reads in an empty file!
with open(get_lib_path() / 'components' / 'metadata_store' / 'category_filter' / 'level2.regex', encoding="utf-8") as f:
    regex = f.read().strip()
    stoplist_expression = re.compile(regex, re.IGNORECASE)


def is_forbidden(txt):
    return bool(stoplist_expression.search(txt))
