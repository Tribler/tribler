#!/usr/bin/env python

# Written by Bram Cohen
# modified by Arno Bakker
# see LICENSE.txt for license information

#
# Arno: ABC put the btmakemetafile in the TorrentMaker directory,
# making it hard to invoke it directly without setting PYTHONPATH
# hence I've create this script for creating torrents here.
#

from TorrentMaker.btmakemetafile import *

if __name__ == '__main__':
    if len(sys.argv) < 3:
        a, b = split(sys.argv[0])
        print 'Usage: ' + b + ' <trackerurl> <file> [file...] [params...]'
        print
        print formatDefinitions(defaults, 80)
        print_announcelist_details()
        print ('')
        sys.exit(2)

    try:
        config, args = parseargs(sys.argv[1:], defaults, 2, None)
        for file in args[1:]:
            make_meta_file(file, args[0], config, progress = prog, fileCallback = file_callback)
    except ValueError, e:
        print 'error: ' + str(e)
        print 'run with no args for parameter explanations'
