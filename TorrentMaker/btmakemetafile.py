#!/usr/bin/env python

# Written by Bram Cohen
# multitracker extensions by John Hoffman
# modified for Merkle hashes and digital signatures by Arno Bakker
# see LICENSE.txt for license information

import sys
import md5
import zlib

from os.path import getsize, split, join, abspath, isdir, normpath
from os import listdir
from sha import sha
from copy import copy
from string import strip
from threading import Event
from time import time
from traceback import print_exc
try:
    from sys import getfilesystemencoding
    ENCODING = getfilesystemencoding()
except:
    from sys import getdefaultencoding
    ENCODING = getdefaultencoding()

from BitTornado.bencode import bencode
from BitTornado.BT1.btformats import check_info
from BitTornado.parseargs import parseargs, formatDefinitions
from Tribler.Merkle.merkle import MerkleTree
from Tribler.Overlay.permid import create_torrent_signature
from Tribler.unicode import str2unicode

defaults = [
    ('announce_list', '', 
        'a list of announce URLs - explained below'), 
    ('httpseeds', '',
        'a list of http seed URLs - explained below'),
    ('piece_size_pow2', 0, 
        "which power of 2 to set the piece size to (0 = automatic)"), 
    ('comment', '', 
        "optional human-readable comment to put in .torrent"), 
    ('filesystem_encoding', '',
        "optional specification for filesystem encoding " +
        "(set automatically in recent Python versions)"),
    ('target', '', 
        "optional target file for the torrent"),
    ('created by', '',
        "optional information on who made the torrent"),
    ('merkle_torrent', 0, 
        "create a Merkle torrent instead of a regular torrent"),
    ('playtime', '',
        "optional play time for video torrents, format [h+:]mm:ss"),
    ('videodim', '',
        "optional dimensions for video torrents, format WIDTHxHEIHT")	
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
    print ('')
    print ('    httpseeds = optional list of http-seed URLs, in the format:')
    print ('            url[|url...]')

def make_meta_file(file, url, params = None, flag = Event(), 
                   progress = lambda x: None, progress_percent = 1, fileCallback = lambda x: None, gethash = None, extradata = {}):
    """ extradata is a dict that is added to the top-level (i.e. metainfo) dict of the torrent """
    if params is None:
        params = {}
    if 'piece_size_pow2' in params:
        piece_len_exp = params['piece_size_pow2']
    else:
        piece_len_exp = default_piece_len_exp
    merkle_torrent = 'merkle_torrent' in params and params['merkle_torrent'] == 1
    if merkle_torrent:
        postfix = '.merkle.torrent'
    else:
        postfix = '.torrent'
    sign = 'permid signature' in params and params['permid signature'] == 1
    if 'target' in params and params['target']:
        f = join(params['target'], split(normpath(file))[1] + postfix)
    else:
        a, b = split(file)
        if b == '':
            f = a + postfix
        else:
            f = join(a, b + postfix)

    if merkle_torrent and piece_len_exp == 0:
        piece_len_exp = 18 # used to be 15=32K, but this works better with slow python
    elif piece_len_exp == 0:  # automatic
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
    
    encoding = None
    if 'filesystem_encoding' in params:
        encoding = params['filesystem_encoding']
    if not encoding:
        encoding = ENCODING
    if not encoding:
        encoding = 'ascii'
    
    playtime = None
    if 'playtime' in params and params['playtime']:
        playtime = params['playtime']

    videodim = None
    if 'videodim' in params and params['videodim']:
        videodim = params['videodim']

    info = makeinfo(file, piece_length, encoding, flag, merkle_torrent, progress, progress_percent, gethash = gethash, playtime = playtime, videodim = videodim)
    if flag.isSet():
        return
    check_info(info)
    h = open(f, 'wb')
    data = {'info': info, 'announce': strip(url), 'encoding': encoding, 'creation date': long(time())}
    data.update(extradata)

    if 'comment' in params and params['comment']:
        data['comment'] = params['comment']
        data['comment.utf-8'] = uniconvert(params['comment'],'utf-8')
    
    if 'created by' in params and params['created by']:
        data['created by'] = params['created by']

    if 'real_announce_list' in params:    # shortcut for progs calling in from outside
        data['announce-list'] = params['real_announce_list']
    elif 'announce_list' in params and params['announce_list']:
        l = []
        for tier in params['announce_list'].split('|'):
            l.append(tier.split(','))
        data['announce-list'] = l
        
    if 'real_httpseeds' in params:    # shortcut for progs calling in from outside
        data['httpseeds'] = params['real_httpseeds']
    elif 'httpseeds' in params and params['httpseeds']:
        data['httpseeds'] = params['httpseeds'].split('|')
        
    if sign:
        create_torrent_signature(data)

    h.write(bencode(data))
    h.close()
    fileCallback(file,f)

def calcsize(file):
    if not isdir(file):
        return getsize(file)
    total = 0L
    for s in subfiles(abspath(file)):
        total += getsize(s[1])
    return total


def uniconvertl(l, e):
    r = []
    try:
        for s in l:
            r.append(uniconvert(s, e))
    except UnicodeError:
        raise UnicodeError('bad filename: '+join(l))
    return r

def uniconvert(s, e):
    if not isinstance(s, unicode):
        try:
            s = str2unicode(s)
        except UnicodeError:
            raise UnicodeError('bad filename: '+s)
    return s.encode(e)

def makeinfo(file, piece_length, encoding, flag, merkle_torrent, progress, progress_percent=1, gethash = None, playtime = None, videodim = None):
    if gethash is None:
        gethash = {}
    
    if not 'md5' in gethash:
        gethash['md5'] = False
    if not 'crc32' in gethash:
        gethash['crc32'] = False
    if not 'sha1' in gethash:
        gethash['sha1'] = False
        
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
            h = open(f, 'rb')

            if gethash['md5']:
                hash_md5 = md5.new()
            if gethash['sha1']:
                hash_sha1 = sha()
            if gethash['crc32']:
                hash_crc32 = zlib.crc32('')
            
            while pos < size:
                a = min(size - pos, piece_length - done)
                
                readpiece = h.read(a)

                # See if the user cancelled
                if flag.isSet():
                    return
                
                sh.update(readpiece)

                # See if the user cancelled
                if flag.isSet():
                    return

                if gethash['md5']:                
                    # Update MD5
                    hash_md5.update(readpiece)
    
                    # See if the user cancelled
                    if flag.isSet():
                        return

                if gethash['crc32']:                
                    # Update CRC32
                    hash_crc32 = zlib.crc32(readpiece, hash_crc32)
    
                    # See if the user cancelled
                    if flag.isSet():
                        return
                
                if gethash['sha1']:                
                    # Update SHA1
                    hash_sha1.update(readpiece)
    
                    # See if the user cancelled
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
                    
            newdict = {'length': size,
                       'path': uniconvertl(p, encoding),
                       'path.utf-8': uniconvertl(p, 'utf-8') }
            if gethash['md5']:
                newdict['md5sum'] = hash_md5.hexdigest()
            if gethash['crc32']:
                newdict['crc32'] = "%08X" % hash_crc32
            if gethash['sha1']:
                newdict['sha1'] = hash_sha1.digest()
                    
            fs.append(newdict)
                    
            h.close()
        if done > 0:
            pieces.append(sh.digest())
        infodict =  { 'piece length': piece_length, 'files': fs, 
                'name': uniconvert(split(file)[1], encoding),
                'name.utf-8': uniconvert(split(file)[1], 'utf-8')}

        if merkle_torrent:
            merkletree = MerkleTree(piece_length,long(totalsize),None,pieces)
            root_hash = merkletree.get_root_hash()
            infodict.update( {'root hash': root_hash } )
        else:
            infodict.update( {'pieces': ''.join(pieces) } )
        return infodict
    else:
        size = getsize(file)
        pieces = []
        p = 0L
        h = open(file, 'rb')
        
        if gethash['md5']:
            hash_md5 = md5.new()
        if gethash['crc32']:
            hash_crc32 = zlib.crc32('')
        if gethash['sha1']:
            hash_sha1 = sha()
        
        while p < size:
            x = h.read(min(piece_length, size - p))

            # See if the user cancelled
            if flag.isSet():
                return
            
            if gethash['md5']:
                # Update MD5
                hash_md5.update(x)
    
                # See if the user cancelled
                if flag.isSet():
                    return
            
            if gethash['crc32']:
                # Update CRC32
                hash_crc32 = zlib.crc32(x, hash_crc32)
    
                # See if the user cancelled
                if flag.isSet():
                    return
            
            if gethash['sha1']:
                # Update SHA-1
                hash_sha1.update(x)
    
                # See if the user cancelled
                if flag.isSet():
                    return
                
            pieces.append(sha(x).digest())

            # See if the user cancelled
            if flag.isSet():
                return

            p += piece_length
            if p > size:
                p = size
            if progress_percent:
                progress(float(p) / size)
            else:
                progress(min(piece_length, size - p))
        h.close()

        newdict = { 'piece length': piece_length, 'length': size, 
                'name': uniconvert(split(file)[1], encoding),
                'name.utf-8': uniconvert(split(file)[1], 'utf-8')}
        if playtime is not None:
            newdict['playtime'] = playtime

        if videodim is not None:
            newdict['videodim'] = videodim

        if merkle_torrent:
            merkletree = MerkleTree(piece_length,size,None,pieces)
            root_hash = merkletree.get_root_hash()
            newdict.update( {'root hash': root_hash } )
        else:
            newdict.update( {'pieces': ''.join(pieces) } )
        if gethash['md5']:
            newdict['md5sum'] = hash_md5.hexdigest()
        if gethash['crc32']:
            newdict['crc32'] = "%08X" % hash_crc32
        if gethash['sha1']:
            newdict['sha1'] = hash_sha1.digest()
                   
        return newdict




def subfiles(d):
    r = []
    stack = [([], d)]
    while stack:
        p, n = stack.pop()
        if isdir(n):
            for s in listdir(n):
                if s not in ignore and s[:1] != '.':
                    stack.append((copy(p) + [s], join(n, s)))
        else:
            r.append((p, n))
    return r

def completedir(dir, url, params = None, flag = Event(),
                vc = lambda x: None, fc = lambda x: None, gethash = None):
    if params is None:
        params = {}
    merkle_torrent = 'merkle_torrent' in params and params['merkle_torrent'] == 1
    if merkle_torrent:
        ext = '.merkle.torrent'
    else:
        ext = '.torrent'
    files = listdir(dir)
    files.sort()
    #if 'target' in params:
    #    target = params['target']
    #else:
    #    target = ''

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
        try:
            t = split(i)[-1]
            if t not in ignore and t[0] != '.':
                #if target != '':
                #    params['target'] = join(target,t+ext)
                make_meta_file(i, url, params, flag, progress = callback, progress_percent = 0, fileCallback = fc, gethash = gethash)
        except ValueError:
            print_exc()

def file_callback(orig, torrent):
    print "Created torrent",torrent,"from",orig

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
            make_meta_file(file, args[0], config, progress = prog, fileCallback = file_callback)
    except ValueError, e:
        print 'error: ' + str(e)
        print 'run with no args for parameter explanations'
