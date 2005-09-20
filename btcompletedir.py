#!/usr/bin/env python

# Written by Bram Cohen
# see LICENSE.txt for license information

from BitTornado import PSYCO
if PSYCO.psyco:
    try:
        import psyco
        assert psyco.__version__ >= 0x010100f0
        psyco.full()
    except:
        pass

from os import listdir
from os.path import join, split
from threading import Event
from sys import argv

from BitTornado.parseargs import parseargs, formatDefinitions

from btmakemetafile import defaults, calcsize, make_meta_file, ignore, print_announcelist_details

def dummy(x):
    pass

def completedir(dir, url, params = {}, flag = Event(), vc = dummy, fc = dummy):
    files = listdir(dir)
    files.sort()
    ext = '.torrent'
    if params.has_key('target'):
        target = params['target']
    else:
        target = ''

    togen = []
    for f in files:
        if f[-len(ext):] != ext and (f + ext) not in files:
            togen.append(join(dir, f))
        
    total = 0
    for i in togen:
        total += calcsize(i)

    subtotal = [0]
    def callback(x, subtotal = subtotal, total = total, vc = vc):
        subtotal[0] += x
        vc(float(subtotal[0]) / total)
    for i in togen:
        fc(i)
        try:
            t = split(i)[-1]
            if t not in ignore and t[0] != '.':
                if target != '':
                    params['target'] = join(target,t+ext)
                make_meta_file(i, url, params, flag, progress = callback, progress_percent = 0)
        except ValueError:
            oldstdout = sys.stdout
            sys.stdout = sys.stderr
            traceback.print_exc()
            sys.stdout = oldstdout

def dc(v):
    print v

if __name__ == '__main__':
    if len(argv) < 3:
        a,b = split(argv[0])
        print 'Usage: ' + b + ' <trackerurl> <dir> [dir...] [params...]'
        print 'makes a .torrent file for every file or directory present in each dir.'
        print
        print formatDefinitions(defaults, 80)
        print_announcelist_details()
        print ('')
        exit(2)

    try:
        config, args = parseargs(argv[1:], defaults, 2, None)
        for dir in args[1:]:
            completedir(dir, args[0], config)
    except ValueError, e:
        print 'error: ' + str(e)
        print 'run with no args for parameter explanations'
