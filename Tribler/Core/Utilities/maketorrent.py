"""
Make torrent.

Author(s): Arno Bakker, Bram Cohen, Arno Bakker
"""
import logging
import os

import chardet
from hashlib import sha1
from copy import copy
from time import time
from libtorrent import bencode


from Tribler.Core.Utilities.unicode import bin2unicode
from Tribler.Core.osutils import fix_filebasename
from Tribler.Core.defaults import tdefdictdefaults
from Tribler.Core.Utilities.utilities import create_valid_metainfo

logger = logging.getLogger(__name__)


def make_torrent_file(input, userabortflag=None, userprogresscallback=lambda x: None):
    """ Create a torrent file from the supplied input.

    Returns a (infohash,metainfo) pair, or (None,None) on userabort. """

    (info, piece_length) = makeinfo(input, userabortflag, userprogresscallback)
    if userabortflag is not None and userabortflag.isSet():
        return None, None
    if info is None:
        return None, None

    metainfo = {'info': info, 'encoding': input['encoding'], 'creation date': long(time())}
    metainfo = create_valid_metainfo(metainfo)

    # http://www.bittorrent.org/beps/bep_0005.html says both announce and nodes
    # are not allowed, but some torrents (Azureus?) apparently violate this.
    if input['nodes'] is None and input['announce'] is None:
        raise ValueError('No tracker set')

    for key in ['announce', 'announce-list', 'nodes', 'comment', 'created by', 'httpseeds', 'url-list']:
        if input[key] is not None and len(input[key]) > 0:
            metainfo[key] = input[key]
            if key == 'comment':
                metainfo['comment.utf-8'] = uniconvert(input['comment'], 'utf-8')

    if 'private' in input:
        metainfo['info']['private'] = input['private']
    if 'anonymous' in input:
        metainfo['info']['anonymous'] = input['anonymous']

    # Two places where infohash calculated, here and in TorrentDef.
    # Elsewhere: must use TorrentDef.get_infohash() to allow P2PURLs.
    infohash = sha1(bencode(info)).digest()
    return infohash, metainfo


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
    sh = sha1()
    done = 0
    fs = []
    totalsize = 0
    totalhashed = 0

    # 1. Determine which files should go into the torrent (=expand any dirs
    # specified by user in input['files']
    subs = []
    for f in input['files']:
        inpath = f['inpath']
        outpath = f['outpath']

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
        size = os.path.getsize(f)
        totalsize += size
        newsubs.append((p, f, size))
    subs = newsubs

    # 3. Calc piece length from totalsize if not set
    if input['piece length'] == 0:
        # Niels we want roughly between 1000-2000 pieces
        # This results in the following logic:

        # We start with 32K pieces
        piece_length = 2 ** 15

        while totalsize / piece_length > 2000:
            # too many piece, double piece_size
            piece_length *= 2
    else:
        piece_length = input['piece length']

    # 4. Read files and calc hashes
    for p, f, size in subs:
        pos = 0

        h = open(f, 'rb')

        while pos < size:
            a = min(size - pos, piece_length - done)

            # See if the user cancelled
            if userabortflag is not None and userabortflag.isSet():
                return None, None

            readpiece = h.read(a)

            # See if the user cancelled
            if userabortflag is not None and userabortflag.isSet():
                return None, None

            sh.update(readpiece)

            done += a
            pos += a
            totalhashed += a

            if done == piece_length:
                pieces.append(sh.digest())
                done = 0
                sh = sha1()

            if userprogresscallback is not None:
                userprogresscallback(float(totalhashed) / float(totalsize))

        newdict = {'length': size,
                   'path': uniconvertl(p, encoding),
                   'path.utf-8': uniconvertl(p, 'utf-8')}

        fs.append(newdict)

        h.close()

    if done > 0:
        pieces.append(sh.digest())

    # 5. Create info dict
    if len(subs) == 1:
        flkey = 'length'
        flval = totalsize
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

    infodict = {'piece length': piece_length,
                flkey: flval,
                'name': uniconvert(name, encoding),
                'name.utf-8': uniconvert(name, 'utf-8')}

    infodict.update({'pieces': ''.join(pieces)})

    return infodict, piece_length


def subfiles(d):
    """ Return list of (pathlist,local filename) tuples for all the files in
    directory 'd' """
    r = []
    stack = [([], d)]
    while stack:
        p, n = stack.pop()
        if os.path.isdir(n):
            for s in os.listdir(n):
                if s[:1] != '.':
                    stack.append((copy(p) + [s], os.path.join(n, s)))
        else:
            r.append((p, n))
    return r


def filename2pathlist(path, skipfirst=False):
    """ Convert a filename to a 'path' entry suitable for a multi-file torrent
    file """
    h = path
    l = []
    while True:
        (h, t) = os.path.split(h)
        if h == '' and t == '':
            break
        if h == '' and skipfirst:
            continue
        if t != '':  # handle case where path ends in / (=path separator)
            l.append(t)

    l.reverse()
    return l


def pathlist2filename(pathlist):
    """ Convert a multi-file torrent file 'path' entry to a filename. """
    fullpath = ''
    for elem in pathlist:
        fullpath = os.path.join(fullpath, elem)

    try:
        return fullpath.decode('utf-8')
    except UnicodeDecodeError:
        charenc = chardet.detect(fullpath)['encoding']
        return fullpath.decode(charenc)


def pathlist2savefilename(pathlist, encoding):
    fullpath = u''
    for elem in pathlist:
        u = bin2unicode(elem, encoding)
        b = fix_filebasename(u)
        fullpath = os.path.join(fullpath, b)
    return fullpath


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


def get_length_filepieceranges_from_metainfo(metainfo, selectedfiles):

    if 'files' not in metainfo['info']:
        # single-file torrent
        return metainfo['info']['length'], None
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
                pieces_range = (offset_to_piece(offset, piecesize, False), offset_to_piece(offset + length, piecesize),
                                (offset - offset_to_piece(offset, piecesize, False) * piecesize), filename)
                filepieceranges.append(pieces_range)
                total += length
            offset += length
        return total, filepieceranges


def offset_to_piece(offset, piece_size, endpoint=True):
    p = offset / piece_size
    if endpoint and offset % piece_size > 0:
        p += 1
    return p


def copy_metainfo_to_input(metainfo, input):
    keys = tdefdictdefaults.keys()
    # Arno: For magnet link support
    keys.append("initial peers")
    for key in keys:
        if key in metainfo:
            input[key] = metainfo[key]

    infokeys = ['name', 'piece length']
    for key in infokeys:
        if key in metainfo['info']:
            input[key] = metainfo['info'][key]

    # Note: don't know inpath, set to outpath
    if 'length' in metainfo['info']:
        outpath = metainfo['info']['name']
        length = metainfo['info']['length']
        d = {'inpath': outpath, 'outpath': outpath, 'length': length}
        input['files'].append(d)
    else:  # multi-file torrent
        files = metainfo['info']['files']
        for file in files:
            outpath = pathlist2filename(file['path'])
            length = file['length']
            d = {'inpath': outpath, 'outpath': outpath, 'length': length}
            input['files'].append(d)

    # Diego : we want web seeding
    if 'url-list' in metainfo:
        input['url-list'] = metainfo['url-list']

    if 'httpseeds' in metainfo:
        input['httpseeds'] = metainfo['httpseeds']
