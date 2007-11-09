# Written by Bram Cohen
# multitracker extensions by John Hoffman
# modified for Merkle hashes and digital signatures by Arno Bakker
# see LICENSE.txt for license information

import sys
import os
import md5
import zlib

from sha import sha
from copy import copy
from threading import Event
from time import time
from traceback import print_exc
from types import LongType

from BitTornado.bencode import bencode
from BitTornado.BT1.btformats import check_info
from Tribler.Merkle.merkle import MerkleTree
from Tribler.Overlay.permid import create_torrent_signature
from Tribler.unicode import str2unicode

ignore = [] # Arno: was ['core', 'CVS']

DEBUG = True

#def print_announcelist_details():
#    print ('    announce_list = optional list of redundant/backup tracker URLs, in the format:')
#    print ('           url[,url...][|url[,url...]...]')
#    print ('                where URLs separated by commas are all tried first')
#    print ('                before the next group of URLs separated by the pipe is checked.')
#    print ("                If none is given, it is assumed you don't want one in the metafile.")
#    print ('                If announce_list is given, clients which support it')
#    print ('                will ignore the <announce> value.')
#    print ('           Examples:')
#    print ('                http://tracker1.com|http://tracker2.com|http://tracker3.com')
#    print ('                     (tries trackers 1-3 in order)')
#    print ('                http://tracker1.com,http://tracker2.com,http://tracker3.com')
#    print ('                     (tries trackers 1-3 in a randomly selected order)')
#    print ('                http://tracker1.com|http://backup1.com,http://backup2.com')
#    print ('                     (tries tracker 1 first, then tries between the 2 backups randomly)')
#    print ('')
#    print ('    httpseeds = optional list of http-seed URLs, in the format:')
#    print ('            url[|url...]')

def make_torrent_file(input, userabortflag = None, userprogresscallback = lambda x: None):
    
    (info,piece_length) = makeinfo(input,userabortflag,userprogresscallback)
    if userabortflag is not None and userabortflag.isSet():
        return (None,None)
    if info is None:
        return (None,None)

    if DEBUG:
        print >>sys.stderr,"mktorrent: makeinfo returned",`info`
    
    check_info(info)
    metainfo = {'info': info, 'encoding': input['encoding'], 'creation date': long(time())}
    
    # See www.bittorrent.org/Draft_DHT_protocol.html
    if len(input['nodes']) == 0:
        metainfo['announce'] = input['announce']
    else:
        metainfo['nodes'] = input['nodes']

    for key in ['announce-list','comment','created by','httpseeds']:
        if len(input[key]) > 0:
            metainfo[key] = input[key]
            if key == 'comment':
                metainfo['comment.utf-8'] = uniconvert(input['comment'],'utf-8')
        
    if input['createtorrentsig']:
        create_torrent_signature(metainfo,input['torrentsigkeypairfilename'])

    # Assuming 1 file, Azureus format no support multi-file torrent with diff
    # bitrates 
    bitrate = None
    for file in input['files']:
        if file['playtime'] is not None:
            secs = parse_playtime_to_secs(file['playtime'])
            bitrate = file['length']/secs
            break

    if bitrate is not None or input['thumb'] is not None:
        thumb = params['thumb']
        mdict = {}
        mdict['Publisher'] = 'Tribler'
        mdict['Description'] = input['comment']
        if bitrate is not None:
            mdict['Progressive'] = 1
            mdict['Speed Bps'] = bitrate
        else:
            mdict['Progressive'] = 0
        mdict['Title'] = metainfo['info']['name']
        mdict['Creation Date'] = long(time())
        # Azureus client source code doesn't tell what this is, so just put in random value from real torrent
        mdict['Content Hash'] = 'PT3GQCPW4NPT6WRKKT25IQD4MU5HM4UY'
        mdict['Revision Date'] = long(time())
        if len(input['thumb']) > 0:
            mdict['Thumbnail'] = thumb
        cdict = {}
        cdict['Content'] = mdict
        metainfo['azureus_properties'] = cdict

    infohash = sha(bencode(info)).digest()
    return (infohash,metainfo)


def calcsize(files):
    total = 0L
    for file in files:
        inpath = file['inpath']
        if os.path.isdir(inpath):
            for s in subfiles(inpath):
                total += os.path.getsize(s[1])
        else:
            total += os.path.getsize(inpath)
    return total

def uniconvertl(l, e):
    r = []
    try:
        for s in l:
            r.append(uniconvert(s, e))
    except UnicodeError:
        raise UnicodeError('bad filename: '+os.path.join(l))
    return r

def uniconvert(s, e):
    if not isinstance(s, unicode):
        try:
            s = str2unicode(s)
        except UnicodeError:
            raise UnicodeError('bad filename: '+s)
    return s.encode(e)


def makeinfo(input,userabortflag,userprogresscallback):
    """ Calculate hashes and create torrent file's 'info' part """
    encoding = input['encoding']

    pieces = []
    sh = sha()
    done = 0L
    fs = []
    totalsize = 0L
    totalhashed = 0L
    
    # 1. Determine which files should go into the torrent (=expand any dirs
    # specified by user in input['files']
    subs = []
    for file in input['files']:
        inpath = file['inpath']
        outpath = file['outpath']
        
        if DEBUG:
            print >>sys.stderr,"makeinfo: inpath",inpath,"outpath",outpath
        
        if os.path.isdir(inpath):
            dirsubs = subfiles(inpath)
            subs.extend(dirsubs)
        else:
            if outpath is None:
                subs.append(([os.path.basename(inpath)],inpath))
            else:
                subs.append((path2list(outpath,skipfirst=True),inpath))
            
    subs.sort()
    
    # 2. Calc total size
    newsubs = []
    for p, f in subs:
        size = os.path.getsize(f)
        totalsize += size
        newsubs.append((p,f,size))
    subs = newsubs

    # 3. Calc piece length from totalsize if not set
    if input['piece length'] == 0:
        if input['createmerkletorrent']:
            # used to be 15=32K, but this works better with slow python
            piece_len_exp = 18 
        else:
            if totalsize > 8L*1024*1024*1024:    # > 8 gig =
                piece_len_exp = 21          #   2 meg pieces
            elif totalsize > 2*1024*1024*1024:   # > 2 gig =
                piece_len_exp = 20          #   1 meg pieces
            elif totalsize > 512*1024*1024:      # > 512M =
                piece_len_exp = 19          #   512K pieces
            elif totalsize > 64*1024*1024:       # > 64M =
                piece_len_exp = 18          #   256K pieces
            elif totalsize > 16*1024*1024:       # > 16M =
                piece_len_exp = 17          #   128K pieces
            elif totalsize > 4*1024*1024:        # > 4M =
                piece_len_exp = 16          #   64K pieces
            else:                           # < 4M =
                piece_len_exp = 15          #   32K pieces
        piece_length = 2 ** piece_len_exp
    else:
        piece_length = input['piece length']

    # 4. Read files and calc hashes
    for p, f, size in subs:
        pos = 0L
        h = open(f, 'rb')

        if input['makehash_md5']:
            hash_md5 = md5.new()
        if input['makehash_sha1']:
            hash_sha1 = sha()
        if input['makehash_crc32']:
            hash_crc32 = zlib.crc32('')
        
        while pos < size:
            a = min(size - pos, piece_length - done)

            # See if the user cancelled
            if userabortflag is not None and userabortflag.isSet():
                return (None,None)
            
            readpiece = h.read(a)

            # See if the user cancelled
            if userabortflag is not None and userabortflag.isSet():
                return (None,None)
            
            sh.update(readpiece)

            if input['makehash_md5']:                
                # Update MD5
                hash_md5.update(readpiece)

            if input['makehash_crc32']:                
                # Update CRC32
                hash_crc32 = zlib.crc32(readpiece, hash_crc32)
            
            if input['makehash_sha1']:                
                # Update SHA1
                hash_sha1.update(readpiece)
            
            done += a
            pos += a
            totalhashed += a
            
            if done == piece_length:
                pieces.append(sh.digest())
                done = 0
                sh = sha()
                
            if userprogresscallback is not None:
                userprogresscallback(float(totalhashed) / float(totalsize))

        newdict = {'length': num2num(size),
                   'path': uniconvertl(p,encoding),
                   'path.utf-8': uniconvertl(p, 'utf-8') }
        
        # Find and add playtime
        for file in input['files']:
            if file['inpath'] == f and file['playtime'] is not None:
                newdict['playtime'] = playtime
                break
        
        if input['makehash_md5']:
            newdict['md5sum'] = hash_md5.hexdigest()
        if input['makehash_crc32']:
            newdict['crc32'] = "%08X" % hash_crc32
        if input['makehash_sha1']:
            newdict['sha1'] = hash_sha1.digest()
        
        fs.append(newdict)
            
        h.close()
            
    if done > 0:
        pieces.append(sh.digest())
       
    # 5. Create info dict         
    if len(subs) == 1:
        flkey = 'length'
        flval = num2num(totalsize)
        name = subs[0][0][0]
    else:
        flkey = 'files'
        flval = fs

        outpath = input['files'][0]['outpath']
        l = path2list(outpath)
        name = l[0]
        
    infodict =  { 'piece length':num2num(piece_length), flkey: flval, 
            'name': uniconvert(name,encoding),
            'name.utf-8': uniconvert(name,'utf-8')}
    
    if input['createmerkletorrent']:
        merkletree = MerkleTree(piece_length,totalsize,None,pieces)
        root_hash = merkletree.get_root_hash()
        infodict.update( {'root hash': root_hash } )
    else:
        infodict.update( {'pieces': ''.join(pieces) } )

    if len(subs) == 1:
        # Find and add playtime
        for file in input['files']:
            if file['inpath'] == f and file['playtime'] is not None:
                infodict['playtime'] = playtime
        
    return (infodict,piece_length)


def subfiles(d):
    r = []
    stack = [([], d)]
    while stack:
        p, n = stack.pop()
        if os.path.isdir(n):
            for s in os.listdir(n):
                if s not in ignore and s[:1] != '.':
                    stack.append((copy(p) + [s], os.path.join(n, s)))
        else:
            r.append((p, n))
    return r

def path2list(path,skipfirst=False):
    h = path
    l = []
    while True:
        (h,t) = os.path.split(h)
        if h == '' and t == '':
            break
        if h == '' and skipfirst:
            continue
        if t != '': # handle case where path ends in / (=path separator)
            l.append(t)
    return l

def num2num(num):
    if type(num) == LongType and num < sys.maxint:
        return int(num)
    else:
        return num


def get_bitrate_from_metainfo(file,metainfo):
    info = metainfo['info']
    if file is None:
        bitrate = None
        try:
            playtime = None
            if info.has_key('playtime'):
                print >>sys.stderr,"TorrentDef: get_bitrate: Bitrate in info field"
                playtime = parse_playtime_to_secs(info['playtime'])
            elif 'playtime' in metainfo: # HACK: encode playtime in non-info part of existing torrent
                print >>sys.stderr,"TorrentDef: get_bitrate: Bitrate in metainfo"
                playtime = parse_playtime_to_secs(metainfo['playtime'])
            elif 'azureus_properties' in metainfo:
                azprop = metainfo['azureus_properties']
                if 'Content' in azprop:
                    content = metainfo['azureus_properties']['Content']
                    if 'Speed Bps' in content:
                        bitrate = float(content['Speed Bps'])
                        print >>sys.stderr,"TorrentDef: get_bitrate: Bitrate in Azureus metainfo",bitrate
            if playtime is not None:
                bitrate = info['length']/playtime
        except:
            print_exc()

        return bitrate

    if file is not None and 'files' in info:
        for i in range(len(info['files'])):
            x = info['files'][i]
                
            intorrentpath = ''
            for elem in x['path']:
                intorrentpath = os.path.join(intorrentpath,elem)
            bitrate = None
            try:
                playtime = None
                if x.has_key('playtime'):
                    playtime = parse_playtime_to_secs(x['playtime'])
                elif 'playtime' in metainfo: # HACK: encode playtime in non-info part of existing torrent
                    playtime = parse_playtime_to_secs(metainfo['playtime'])
                    
                if playtime is not None:
                    bitrate = x['length']/playtime
            except:
                print_exc()
                
            if intorrentpath == file:
                return bitrate
            
        raise ValueError("File not found in torrent")
    else:
        raise ValueError("File not found in single-file torrent")
