import linecache
import sys

original_updatecache = linecache.updatecache


def patched_updatecache(filename, *args, **kwargs):
    if getattr(sys, 'frozen', False):
        # When Tribler runs from a bundle, Tribler sources are available inside the `tribler_source` subfolder
        if filename.startswith('src\\tribler'):  # Relative path with cx_freeze on Windows
            filename = 'tribler_source' + filename[3:]  # Replacing `src\\` -> `tribler_source\\`
        elif filename.startswith('tribler/'):  # Relative path with PyInstaller on Mac/Linux:
            filename = 'tribler_source/' + filename  # Appending `tribler_source/` to the relative path
    result = original_updatecache(filename, *args, **kwargs)
    return result


patched_updatecache.patched = True


def patch():
    if getattr(linecache.updatecache, 'patched', False):
        return

    linecache.updatecache = patched_updatecache
