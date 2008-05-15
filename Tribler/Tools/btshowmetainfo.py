#!/usr/bin/env python

# Written by Henry 'Pi' James and Loring Holden
# modified for multitracker display by John Hoffman
# see LICENSE.txt for license information

from sys import *
from os.path import *
from sha import *
from Tribler.Core.BitTornado.bencode import *
from Tribler.Core.Overlay.permid import verify_torrent_signature

if len(argv) == 1:
    print '%s file1.torrent file2.torrent file3.torrent ...' % argv[0]
    print
    exit(2) # common exit code for syntax error

for metainfo_name in argv[1:]:
    metainfo_file = open(metainfo_name, 'rb')
    metainfo = bdecode(metainfo_file.read())
    print "metainfo:",metainfo.keys()
    #print "metainfo creation date",metainfo['creation date']
    if 'azureus_properties' in metainfo:
        azprop = metainfo['azureus_properties']
        print "azprop:",azprop.keys()
        if 'Content' in azprop:
                content = azprop['Content']
                print "content:",content.keys()
                for key in content.keys():
                        if key.lower() != 'thumbnail':
                                print key,"=",content[key]
        if 'cdn_properties' in azprop:
            cdnprops = azprop['cdn_properties']
            print "cdn_properties:",cdnprops.keys()
            for key in cdnprops:
                print "cdn_properties:",key,"=",cdnprops[key]
    #print `metainfo`
    info = metainfo['info']
    info_hash = sha(bencode(info))

    print 'metainfo file.: %s' % basename(metainfo_name)
    print 'info hash.....: %s' % info_hash.hexdigest()
    print 'info hash.....: %s' % `info_hash.digest()`
    piece_length = info['piece length']
    if info.has_key('length'):
        # let's assume we just have a file
        print 'file name.....: %s' % info['name']
        file_length = info['length']
        name ='file size.....:'
    else:
        # let's assume we have a directory structure
        print 'directory name: %s' % info['name']
        print 'files.........: '
        file_length = 0;
        for file in info['files']:
            path = ''
            for item in file['path']:
                if (path != ''):
                   path = path + "/"
                path = path + item
            print '   %s (%d)' % (path, file['length'])
            file_length += file['length']
            name ='archive size..:'
    piece_number, last_piece_length = divmod(file_length, piece_length)
    print '%s %i (%i * %i + %i)' \
          % (name,file_length, piece_number, piece_length, last_piece_length)
    if info.has_key('root hash'):
        print 'root hash.....: %s' % `info['root hash']`
    if info.has_key('live'):
        print 'torrent type..: live',`info['live']`
    
    print 'announce url..: %s' % metainfo['announce']
    if metainfo.has_key('announce-list'):
        list = []
        for tier in metainfo['announce-list']:
            for tracker in tier:
                list+=[tracker,',']
            del list[-1]
            list+=['|']
        del list[-1]
        liststring = ''
        for i in list:
            liststring+=i
        print 'announce-list.: %s' % liststring
    if metainfo.has_key('httpseeds'):
        list = []
        for seed in metainfo['httpseeds']:
            list += [seed,'|']
        del list[-1]
        liststring = ''
        for i in list:
            liststring+=i
        print 'http seeds....: %s' % liststring
    # Torrent signature
    if metainfo.has_key('signature'):
        print 'signature.....: %s' % `metainfo['signature']`
    if metainfo.has_key('signer'):
        print 'signer........: %s' % `metainfo['signer']`
    if metainfo.has_key('signature') and metainfo.has_key('signer'):
        if verify_torrent_signature(metainfo):
            res = 'OK'
        else:
            res = 'Failed'
        print 'signaturecheck: %s' % res
    if metainfo.has_key('comment'):
        print 'comment.......: %s' % metainfo['comment']
