# Written by Arno Bakker, Bram Cohen
# multitracker extensions by John Hoffman
# modified for Merkle hashes and digital signatures by Arno Bakker
# see LICENSE.txt for license information

import sys
import os
from hashlib import md5
import zlib
import logging

from Tribler.Core.Utilities.Crypto import sha
from copy import copy
from time import time
from traceback import print_exc
from types import LongType

from Tribler.Core.Utilities.bencode import bencode
from Tribler.Core.Merkle.merkle import MerkleTree
from Tribler.Core.Utilities.unicode import str2unicode, bin2unicode
from Tribler.Core.APIImplementation.miscutils import parse_playtime_to_secs, offset2piece
from Tribler.Core.osutils import fix_filebasename
from Tribler.Core.defaults import tdefdictdefaults
from Tribler.Core.Utilities.utilities import validTorrentFile


ignore = []  # Arno: was ['core', 'CVS']

logger = logging.getLogger(__name__)

def make_torrent_file(input, userabortflag=None, userprogresscallback=lambda x: None):
    """ Create a torrent file from the supplied input.

    Returns a (infohash,metainfo) pair, or (None,None) on userabort. """

    (info, piece_length) = makeinfo(input, userabortflag, userprogresscallback)
    if userabortflag is not None and userabortflag.isSet():
        return (None, None)
    if info is None:
        return (None, None)

    # if DEBUG:
    #    print >>sys.stderr,"mktorrent: makeinfo returned",`info`

    metainfo = {'info': info, 'encoding': input['encoding'], 'creation date': long(time())}
    validTorrentFile(metainfo)

    # http://www.bittorrent.org/DHT_protocol.html says both announce and nodes
    # are not allowed, but some torrents (Azureus?) apparently violate this.
    if input['nodes'] is None and input['announce'] is None:
        raise ValueError('No tracker set')

    for key in ['announce', 'announce-list', 'nodes', 'comment', 'created by', 'httpseeds', 'url-list']:
        if input[key] is not None and len(input[key]) > 0:
            metainfo[key] = input[key]
            if key == 'comment':
                metainfo['comment.utf-8'] = uniconvert(input['comment'], 'utf-8')

    # Assuming 1 file, Azureus format no support multi-file torrent with diff
    # bitrates
    bitrate = None
    for file in input['files']:
        if file['playtime'] is not None:
            secs = parse_playtime_to_secs(file['playtime'])
            bitrate = file['length'] / secs
            break
        if input.get('bps') is not None:
            bitrate = input['bps']
            break

    if bitrate is not None or input['thumb'] is not None:
        mdict = {}
        mdict['Publisher'] = 'Tribler'
        if input['comment'] is None:
            descr = ''
        else:
            descr = input['comment']
        mdict['Description'] = descr

        if bitrate is not None:
            mdict['Progressive'] = 1
            mdict['Speed Bps'] = int(bitrate)  # bencode fails for float
        else:
            mdict['Progressive'] = 0

        mdict['Title'] = metainfo['info']['name']
        mdict['Creation Date'] = long(time())
        # Azureus client source code doesn't tell what this is, so just put in random value from real torrent
        mdict['Content Hash'] = 'PT3GQCPW4NPT6WRKKT25IQD4MU5HM4UY'
        mdict['Revision Date'] = long(time())
        if input['thumb'] is not None:
            mdict['Thumbnail'] = input['thumb']
        cdict = {}
        cdict['Content'] = mdict
        metainfo['azureus_properties'] = cdict

    if input['torrentsigkeypairfilename'] is not None:
        from Tribler.Core.Overlay.permid import create_torrent_signature

        create_torrent_signature(metainfo, input['torrentsigkeypairfilename'])

    if 'url-compat' in input:
        metainfo['info']['url-compat'] = input['url-compat']

    # Arno, 2010-03-02:
    # Theoretically should go into 'info' field, to get infohash protection
    # because the video won't play without them. In the future we'll sign
    # the whole .torrent IMHO so it won't matter. Keeping it out of 'info'
    # at the moment makes the .tstream files more stable (in case you restart
    # the live source, and the Ogg header generated contains some date or
    # what not, we'd need a new .tstream to be distributed to all.
    #
    if 'ogg-headers' in input:
        metainfo['ogg-headers'] = input['ogg-headers']

    # Two places where infohash calculated, here and in TorrentDef.
    # Elsewhere: must use TorrentDef.get_infohash() to allow P2PURLs.
    infohash = sha(bencode(info)).digest()
    return (infohash, metainfo)


def uniconvertl(l, e):
    """ Convert a pathlist to a list of strings encoded in encoding "e" using
    uniconvert. """
    r = []
    try:
        for s in l:
            r.append(uniconvert(s, e))
    except UnicodeError:
        raise UnicodeError('bad filename: ' + os.path.join(l))
    return r


def uniconvert(s, enc):
    """ Convert 's' to a string containing a Unicode sequence encoded using
    encoding "enc". If 's' is not a Unicode object, we first try to convert
    it to one, guessing the encoding if necessary. """
    if not isinstance(s, unicode):
        try:
            s = bin2unicode(s, enc)
        except UnicodeError:
            raise UnicodeError('bad filename: ' + s)
    return s.encode(enc)


def makeinfo(input, userabortflag, userprogresscallback):
    """ Calculate hashes and create torrent file's 'info' part """
    encoding = input['encoding']

    pieces = []
    sh = sha()
    done = 0
    fs = []
    totalsize = 0
    totalhashed = 0

    # 1. Determine which files should go into the torrent (=expand any dirs
    # specified by user in input['files']
    subs = []
    for file in input['files']:
        inpath = file['inpath']
        outpath = file['outpath']

        logger.debug("makeinfo: inpath=%s, outpath=%s", inpath, outpath)

        if os.path.isdir(inpath):
            dirsubs = subfiles(inpath)
            subs.extend(dirsubs)
        else:
            if outpath is None:
                subs.append(([os.path.basename(inpath)], inpath))
            else:
                subs.append((filename2pathlist(outpath, skipfirst=True), inpath))

    subs.sort()

    # 2. Calc total size
    newsubs = []
    for p, f in subs:
        if 'live' in input:
            size = input['files'][0]['length']
        else:
            size = os.path.getsize(f)
        totalsize += size
        newsubs.append((p, f, size))
    subs = newsubs

    # 3. Calc piece length from totalsize if not set
    if input['piece length'] == 0:
        if input['createmerkletorrent']:
            # used to be 15=32K, but this works better with slow python
            piece_length = 2 ** 18
        else:
            # Niels we want roughly between 1000-2000 pieces
            # This results in the following logic:

            # We start with 32K pieces
            piece_length = 2 ** 15

            while totalsize / piece_length > 2000:
                # too many piece, double piece_size
                piece_length *= 2
    else:
        piece_length = input['piece length']

    # 4. Read files and calc hashes, if not live
    if 'live' not in input:
        for p, f, size in subs:
            pos = 0

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
                    return (None, None)

                readpiece = h.read(a)

                # See if the user cancelled
                if userabortflag is not None and userabortflag.isSet():
                    return (None, None)

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
                       'path': uniconvertl(p, encoding),
                       'path.utf-8': uniconvertl(p, 'utf-8')}

            # Find and add playtime
            for file in input['files']:
                if file['inpath'] == f:
                    if file['playtime'] is not None:
                        newdict['playtime'] = file['playtime']
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

        if 'name' in input:  # allow someone to overrule the default name if multifile
            name = input['name']
        else:
            outpath = input['files'][0]['outpath']
            l = filename2pathlist(outpath)
            name = l[0]

    infodict = {'piece length': num2num(piece_length), flkey: flval,
            'name': uniconvert(name, encoding),
            'name.utf-8': uniconvert(name, 'utf-8')}

    if 'live' not in input:

        if input['createmerkletorrent']:
            merkletree = MerkleTree(piece_length, totalsize, None, pieces)
            root_hash = merkletree.get_root_hash()
            infodict.update({'root hash': root_hash})
        else:
            infodict.update({'pieces': ''.join(pieces)})
    else:
        # With source auth, live is a dict
        infodict['live'] = input['live']

    if 'cs_keys' in input:
        # This is a closed swarm - add torrent keys
        infodict['cs_keys'] = input['cs_keys']

    if 'ns-metadata' in input:
        # This has P2P-Next metadata, store in info field to make it
        # immutable.
        infodict['ns-metadata'] = input['ns-metadata']

    if len(subs) == 1:
        # Find and add playtime
        for file in input['files']:
            if file['inpath'] == f:
                if file['playtime'] is not None:
                    infodict['playtime'] = file['playtime']

    return (infodict, piece_length)


def subfiles(d):
    """ Return list of (pathlist,local filename) tuples for all the files in
    directory 'd' """
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


def filename2pathlist(path, skipfirst=False):
    """ Convert a filename to a 'path' entry suitable for a multi-file torrent
    file """
    # if DEBUG:
    #    print >>sys.stderr,"mktorrent: filename2pathlist:",path,skipfirst

    h = path
    l = []
    while True:
        # if DEBUG:
        #    print >>sys.stderr,"mktorrent: filename2pathlist: splitting",h

        (h, t) = os.path.split(h)
        if h == '' and t == '':
            break
        if h == '' and skipfirst:
            continue
        if t != '':  # handle case where path ends in / (=path separator)
            l.append(t)

    l.reverse()
    # if DEBUG:
    #    print >>sys.stderr,"mktorrent: filename2pathlist: returning",l

    return l


def pathlist2filename(pathlist):
    """ Convert a multi-file torrent file 'path' entry to a filename. """
    fullpath = ''
    for elem in pathlist:
        fullpath = os.path.join(fullpath, elem)
    return fullpath

def pathlist2savefilename(pathlist, encoding):
    fullpath = u''
    for elem in pathlist:
        u = bin2unicode(elem, encoding)
        b = fix_filebasename(u)
        fullpath = os.path.join(fullpath, b)
    return fullpath

def torrentfilerec2savefilename(filerec, length=None):
    if length is None:
        length = len(filerec['path'])
    if 'path.utf-8' in filerec:
        key = 'path.utf-8'
        encoding = 'utf-8'
    else:
        key = 'path'
        encoding = None

    return pathlist2savefilename(filerec[key][:length], encoding)

def savefilenames2finaldest(fn1, fn2):
    """ Returns the join of two savefilenames, possibly shortened
    to adhere to OS specific limits.
    """
    j = os.path.join(fn1, fn2)
    if sys.platform == 'win32':
        # Windows has a maximum path length of 260
        # http://msdn2.microsoft.com/en-us/library/aa365247.aspx
        j = j[:259]  # 260 don't work.
    return j


def num2num(num):
    """ Converts long to int if small enough to fit """
    if isinstance(num, LongType) and num < sys.maxsize:
        return int(num)
    else:
        return num

def get_torrentfilerec_from_metainfo(filename, metainfo):
    info = metainfo['info']
    if filename is None:
        return info

    if filename is not None and 'files' in info:
        for i in range(len(info['files'])):
            x = info['files'][i]

            intorrentpath = pathlist2filename(x['path'])
            if intorrentpath == filename:
                return x

        raise ValueError("File not found in torrent")
    else:
        raise ValueError("File not found in single-file torrent")


def get_bitrate_from_metainfo(file, metainfo):
    info = metainfo['info']
    if file is None or 'files' not in info:  # if no file is specified or this is a single file torrent
        bitrate = None
        try:
            playtime = None
            if 'playtime' in info:
                # print >>sys.stderr,"TorrentDef: get_bitrate: Bitrate in info field"
                playtime = parse_playtime_to_secs(info['playtime'])
            elif 'playtime' in metainfo:  # HACK: encode playtime in non-info part of existing torrent
                # print >>sys.stderr,"TorrentDef: get_bitrate: Bitrate in metainfo"
                playtime = parse_playtime_to_secs(metainfo['playtime'])
            elif 'azureus_properties' in metainfo:
                azprop = metainfo['azureus_properties']
                if 'Content' in azprop:
                    content = metainfo['azureus_properties']['Content']
                    if 'Speed Bps' in content:
                        bitrate = float(content['Speed Bps'])
                        # print >>sys.stderr,"TorrentDef: get_bitrate: Bitrate in Azureus metainfo",bitrate
            if playtime is not None:
                bitrate = info['length'] / playtime
                logger.debug("TorrentDef: get_bitrate: Found bitrate %s", bitrate)
        except:
            print_exc()

        return bitrate

    else:
        for i in range(len(info['files'])):
            x = info['files'][i]

            intorrentpath = ''
            for elem in x['path']:
                intorrentpath = os.path.join(intorrentpath, elem)
            bitrate = None
            try:
                playtime = None
                if 'playtime' in x:
                    playtime = parse_playtime_to_secs(x['playtime'])
                elif 'playtime' in metainfo:  # HACK: encode playtime in non-info part of existing torrent
                    playtime = parse_playtime_to_secs(metainfo['playtime'])
                elif 'azureus_properties' in metainfo:
                    azprop = metainfo['azureus_properties']
                    if 'Content' in azprop:
                        content = metainfo['azureus_properties']['Content']
                        if 'Speed Bps' in content:
                            bitrate = float(content['Speed Bps'])
                            # print >>sys.stderr,"TorrentDef: get_bitrate: Bitrate in Azureus metainfo",bitrate

                if playtime is not None:
                    bitrate = x['length'] / playtime
            except:
                print_exc()

            if intorrentpath == file:
                return bitrate

        raise ValueError("File not found in torrent")


def get_length_from_metainfo(metainfo, selectedfiles):
    if 'files' not in metainfo['info']:
        # single-file torrent
        return metainfo['info']['length']
    else:
        # multi-file torrent
        files = metainfo['info']['files']

        total = 0
        for i in xrange(len(files)):
            path = files[i]['path']
            length = files[i]['length']
            if length > 0 and (not selectedfiles or pathlist2filename(path) in selectedfiles):
                total += length
        return total


def get_length_priority_from_metainfo(metainfo, selectedfiles):
    if 'files' not in metainfo['info']:
        # single-file torrent
        return (metainfo['info']['length'], "")
    else:
        # multi-file torrent
        files = metainfo['info']['files']

        total = 0
        priorities = []
        for i in xrange(len(files)):
            path = files[i]['path']
            length = files[i]['length']

            if length > 0 and (not selectedfiles or pathlist2filename(path) in selectedfiles):
                priorities.append("1")
                total += length
            else:
                priorities.append("-1")
        return (total, ",".join(priorities))

def get_length_filepieceranges_from_metainfo(metainfo, selectedfiles):

    if 'files' not in metainfo['info']:
        # single-file torrent
        return (metainfo['info']['length'], None)
    else:
        # multi-file torrent
        files = metainfo['info']['files']
        piecesize = metainfo['info']['piece length']

        offset = 0
        total = 0
        filepieceranges = []
        for i in xrange(len(files)):
            path = files[i]['path']
            length = files[i]['length']
            filename = pathlist2filename(path)

            if length > 0 and (not selectedfiles or (selectedfiles and filename in selectedfiles)):
                range = (offset2piece(offset, piecesize, False), offset2piece(offset + length, piecesize), (offset - offset2piece(offset, piecesize, False) * piecesize), filename)
                filepieceranges.append(range)
                total += length
            offset += length
        return (total, filepieceranges)


def copy_metainfo_to_input(metainfo, input):

    keys = tdefdictdefaults.keys()
    # Arno: For magnet link support
    keys.append("initial peers")
    for key in keys:
        if key in metainfo:
            input[key] = metainfo[key]

    infokeys = ['name', 'piece length', 'live', 'url-compat']
    for key in infokeys:
        if key in metainfo['info']:
            input[key] = metainfo['info'][key]

    # Note: don't know inpath, set to outpath
    if 'length' in metainfo['info']:
        outpath = metainfo['info']['name']
        if 'playtime' in metainfo['info']:
            playtime = metainfo['info']['playtime']
        else:
            playtime = None
        length = metainfo['info']['length']
        d = {'inpath': outpath, 'outpath': outpath, 'playtime':playtime, 'length':length}
        input['files'].append(d)
    else:  # multi-file torrent
        files = metainfo['info']['files']
        for file in files:
            outpath = pathlist2filename(file['path'])
            if 'playtime' in file:
                playtime = file['playtime']
            else:
                playtime = None
            length = file['length']
            d = {'inpath': outpath, 'outpath': outpath, 'playtime':playtime, 'length':length}
            input['files'].append(d)

    if 'azureus_properties' in metainfo:
        azprop = metainfo['azureus_properties']
        if 'Content' in azprop:
            content = metainfo['azureus_properties']['Content']
            if 'Thumbnail' in content:
                input['thumb'] = content['Thumbnail']

    if 'live' in metainfo['info']:
        input['live'] = metainfo['info']['live']

    if 'cs_keys' in metainfo['info']:
        input['cs_keys'] = metainfo['info']['cs_keys']

    if 'url-compat' in metainfo['info']:
        input['url-compat'] = metainfo['info']['url-compat']

    if 'ogg-headers' in metainfo:
        input['ogg-headers'] = metainfo['ogg-headers']

    if 'ns-metadata' in metainfo['info']:
        input['ns-metadata'] = metainfo['info']['ns-metadata']

    # Diego : we want web seeding
    if 'url-list' in metainfo:
        input['url-list'] = metainfo['url-list']

    if 'httpseeds' in metainfo:
        input['httpseeds'] = metainfo['httpseeds']


def get_files(metainfo, exts):
    # 01/02/10 Boudewijn: now returns (file, length) tuples instead of files

    videofiles = []
    if 'files' in metainfo['info']:
        # Multi-file torrent
        files = metainfo['info']['files']
        for file in files:

            p = file['path']
            # print >>sys.stderr,"TorrentDef: get_files: file is",p
            filename = ''
            for elem in p:
                # print >>sys.stderr,"TorrentDef: get_files: elem is",elem
                filename = os.path.join(filename, elem)

            # print >>sys.stderr,"TorrentDef: get_files: composed filename is",filename
            (prefix, ext) = os.path.splitext(filename)
            if ext != '' and ext[0] == '.':
                ext = ext[1:]
            # print >>sys.stderr,"TorrentDef: get_files: ext",ext
            if exts is None or ext.lower() in exts:
                videofiles.append((filename, file['length']))
    else:
        # print >>sys.stderr,"TorrentDef: get_files: Single-torrent file"

        filename = metainfo['info']['name']  # don't think we need fixed name here
        (prefix, ext) = os.path.splitext(filename)
        if ext != '' and ext[0] == '.':
            ext = ext[1:]
        if exts is None or ext.lower() in exts:
            videofiles.append((filename, metainfo['info']['length']))
    return videofiles
