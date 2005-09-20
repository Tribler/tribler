#!/usr/bin/env python

# Written by Bram Cohen
# multitracker extensions by John Hoffman
# see LICENSE.txt for license information

from BitTornado import PSYCO
if PSYCO.psyco:
    try:
        import psyco
        assert psyco.__version__ >= 0x010100f0
        psyco.full()
    except:
        pass

import sys
from os.path import getsize, split, join, abspath, isdir
from os import listdir
from sha import sha
from copy import copy
from string import strip
from threading import Event
from time import time

from BitTornado.bencode import bencode
from BitTornado.BT1.btformats import check_info
from BitTornado.parseargs import parseargs, formatDefinitions

defaults = [
    ('announce_list', '', 
        'a list of announce URLs - explained below'), 
    ('piece_size_pow2', 0, 
        "which power of 2 to set the piece size to (0 = automatic)"), 
    ('comment', '', 
        "optional human-readable comment to put in .torrent"), 
    ('target', '', 
        "optional target file for the torrent")
    ]

default_piece_len_exp = 18

ignore = ['core', 'CVS']

def print_announcelist_details():
    print ('    announce_list = optional list of redundant/backup tracker URLs, in the format:')
    print ('           url[,url...][|url[,url...]...]')
    print ('                where URLs separated by commas are all tried first')
    print ('                before the next group of URLs separated by the pipe is checked.')
    print ("                If none is given, it is assumed you don't want one in the metafile.")
    print ('                If announce_list is given, clients which support it')
    print ('                will ignore the <announce> value.')
    print ('           Examples:')
    print ('                http://tracker1.com|http://tracker2.com|http://tracker3.com')
    print ('                     (tries trackers 1-3 in order)')
    print ('                http://tracker1.com,http://tracker2.com,http://tracker3.com')
    print ('                     (tries trackers 1-3 in a randomly selected order)')
    print ('                http://tracker1.com|http://backup1.com,http://backup2.com')
    print ('                     (tries tracker 1 first, then tries between the 2 backups randomly)')

def dummy(v):
    pass

def make_meta_file(file, url, params = {}, flag = Event(), 
                   progress = dummy, progress_percent = 1):
    if params.has_key('piece_size_pow2'):
        piece_len_exp = params['piece_size_pow2']
    else:
        piece_len_exp = default_piece_len_exp
    if params.has_key('target') and params['target'] != '':
        f = params['target']
    else:
        a, b = split(file)
        if b == '':
            f = a + '.torrent'
        else:
            f = join(a, b + '.torrent')
            
    if piece_len_exp == 0:  # automatic
        size = calcsize(file)
        if   size > 8L*1024*1024*1024:   # > 8 gig =
            piece_len_exp = 21          #   2 meg pieces
        elif size > 2*1024*1024*1024:   # > 2 gig =
            piece_len_exp = 20          #   1 meg pieces
        elif size > 512*1024*1024:      # > 512M =
            piece_len_exp = 19          #   512K pieces
        elif size > 64*1024*1024:       # > 64M =
            piece_len_exp = 18          #   256K pieces
        elif size > 16*1024*1024:       # > 16M =
            piece_len_exp = 17          #   128K pieces
        elif size > 4*1024*1024:        # > 4M =
            piece_len_exp = 16          #   64K pieces
        else:                           # < 4M =
            piece_len_exp = 15          #   32K pieces
    piece_length = 2 ** piece_len_exp
    
    info = makeinfo(file, piece_length, flag, progress, progress_percent)
    if flag.isSet():
        return
    check_info(info)
    h = open(f, 'wb')
    data = {'info': info, 'announce': strip(url), 'creation date': long(time())}
    if params.has_key('comment') and params['comment'] != '':
        data['comment'] = params['comment']
    if params.has_key('real_announce_list'):    # shortcut for progs calling in from outside
        data['announce-list'] = params['real_announce_list']
    elif params.has_key('announce_list') and params['announce_list'] != '':
        list = []
        for tier in params['announce_list'].split('|'):
            sublist = []
            for tracker in tier.split(','):
                sublist += [tracker]
            list += [sublist]
        data['announce-list'] = list
        
    h.write(bencode(data))
    h.close()

def calcsize(file):
    if not isdir(file):
        return getsize(file)
    total = 0L
    for s in subfiles(abspath(file)):
        total += getsize(s[1])
    return total

def makeinfo(file, piece_length, flag, progress, progress_percent=1):
    file = abspath(file)
    if isdir(file):
        subs = subfiles(file)
        subs.sort()
        pieces = []
        sh = sha()
        done = 0L
        fs = []
        totalsize = 0.0
        totalhashed = 0L
        for p, f in subs:
            totalsize += getsize(f)

        for p, f in subs:
            pos = 0L
            size = getsize(f)
            fs.append({'length': size, 'path': p})
            h = open(f, 'rb')
            while pos < size:
                a = min(size - pos, piece_length - done)
                sh.update(h.read(a))
                if flag.isSet():
                    return
                done += a
                pos += a
                totalhashed += a
                
                if done == piece_length:
                    pieces.append(sh.digest())
                    done = 0
                    sh = sha()
                if progress_percent:
                    progress(totalhashed / totalsize)
                else:
                    progress(a)
            h.close()
        if done > 0:
            pieces.append(sh.digest())
        return {'pieces': ''.join(pieces), 
            'piece length': piece_length, 'files': fs, 
            'name': split(file)[1]}
    else:
        size = getsize(file)
        pieces = []
        p = 0L
        h = open(file, 'rb')
        while p < size:
            x = h.read(min(piece_length, size - p))
            if flag.isSet():
                return
            pieces.append(sha(x).digest())
            p += piece_length
            if p > size:
                p = size
            if progress_percent:
                progress(float(p) / size)
            else:
                progress(min(piece_length, size - p))
        h.close()
        return {'pieces': ''.join(pieces), 
            'piece length': piece_length, 'length': size, 
            'name': split(file)[1]}

def subfiles(d):
    r = []
    stack = [([], d)]
    while len(stack) > 0:
        p, n = stack.pop()
        if isdir(n):
            for s in listdir(n):
                if s not in ignore and s[:1] != '.':
                    stack.append((copy(p) + [s], join(n, s)))
        else:
            r.append((p, n))
    return r

def prog(amount):
    print '%.1f%% complete\r' % (amount * 100), 

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
            make_meta_file(file, args[0], config, progress = prog)
    except ValueError, e:
        print 'error: ' + str(e)
        print 'run with no args for parameter explanations'
