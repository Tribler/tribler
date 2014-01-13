#!/usr/bin/env python

# Written by Henry 'Pi' James and Loring Holden
# modified for multitracker display by John Hoffman
# see LICENSE.txt for license information

from sys import *
from os.path import *
import binascii

from Tribler.Core.API import TorrentDef
from Tribler.Core.Overlay.permid import verify_torrent_signature

if len(argv) == 1:
    print('%s file1.torrent file2.torrent file3.torrent ...' % argv[0])
    print()
    exit(2)  # common exit code for syntax error

for metainfo_name in argv[1:]:
    if metainfo_name.endswith(".url"):
        f = open(metainfo_name, "rb")
        url = f.read()
        f.close()
        tdef = TorrentDef.load_from_url(url)
    else:
        tdef = TorrentDef.load(metainfo_name)
    metainfo = tdef.get_metainfo()
    infohash = tdef.get_infohash()

    print("metainfo:", metainfo.keys())
    # print "metainfo creation date",metainfo['creation date']
    if 'azureus_properties' in metainfo:
        azprop = metainfo['azureus_properties']
        print("azprop:", azprop.keys())
        if 'Content' in azprop:
            content = azprop['Content']
            print("content:", content.keys())
            for key in content.keys():
                if key.lower() != 'thumbnail':
                    print(key, "=", content[key])
        if 'cdn_properties' in azprop:
            cdnprops = azprop['cdn_properties']
            print("cdn_properties:", cdnprops.keys())
            for key in cdnprops:
                print("cdn_properties:", key, "=", cdnprops[key])
    # print `metainfo`
    info = metainfo['info']

    print('metainfo file.: %s' % basename(metainfo_name))
    print('info hash.....: %s' % binascii.hexlify(infohash))
    print('info hash.....: %s' % repr(infohash))
    piece_length = info['piece length']
    if 'length' in info:
        # let's assume we just have a file
        print('file name.....: %s' % info['name'])
        file_length = info['length']
        name = 'file size.....:'
    else:
        # let's assume we have a directory structure
        print('directory name: %s' % info['name'])
        print('files.........: ')
        file_length = 0
        for file in info['files']:
            path = ''
            for item in file['path']:
                if (path != ''):
                    path = path + "/"
                path = path + item
            print('   %s (%d)' % (path, file['length']))
            file_length += file['length']
            name = 'archive size..:'
    piece_number, last_piece_length = divmod(file_length, piece_length)
    print('%s %i (%i * %i + %i)' \
          % (name, file_length, piece_number, piece_length, last_piece_length))
    if 'root hash' in info:
        print('root hash.....: %s' % repr(info['root hash']))
    if 'live' in info:
        print('torrent type..: live', repr(info['live']))

    print('announce url..: %s' % metainfo['announce'])
    if 'announce-list' in metainfo:
        list = []
        for tier in metainfo['announce-list']:
            for tracker in tier:
                list += [tracker, ',']
            del list[-1]
            list += ['|']
        del list[-1]
        liststring = ''
        for i in list:
            liststring += i
        print('announce-list.: %s' % liststring)
    if 'httpseeds' in metainfo:
        list = []
        for seed in metainfo['httpseeds']:
            list += [seed, '|']
        del list[-1]
        liststring = ''
        for i in list:
            liststring += i
        print('http seeds....: %s' % liststring)
    if 'url-list' in metainfo:
        list = []
        for seed in metainfo['url-list']:
            list += [seed, '|']
        del list[-1]
        liststring = ''
        for i in list:
            liststring += i
        print('url-list......: %s' % liststring)

    # Torrent signature
    if 'signature' in metainfo:
        print('signature.....: %s' % repr(metainfo['signature']))
    if 'signer' in metainfo:
        print('signer........: %s' % repr(metainfo['signer']))
    if 'signature' in metainfo and 'signer' in metainfo:
        if verify_torrent_signature(metainfo):
            res = 'OK'
        else:
            res = 'Failed'
        print('signaturecheck: %s' % res)
    if 'comment' in metainfo:
        print('comment.......: %s' % metainfo['comment'])
