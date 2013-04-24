# Written by Yuan Yuan
# see LICENSE.txt for license information

import sys, os
execpath = os.path.join(os.path.abspath(os.path.dirname(sys.argv[0])), '..', '..')
sys.path.append(execpath)
#print sys.path
from Utility.utility import getMetainfo
from Tribler.Category.Category import Category

DEBUG = False

def testFilter(catfilename, torrentpath):
    readCategorisationFile(catfilename)
    #print 'Install_dir is %s' % execpath
    c = Category.getInstance(execpath, None)
    total = porn = fn = fp = 0
    for tfilename,isporn in tdict.items():
        torrent = getMetainfo(os.path.join(torrentpath,tfilename))
        name = torrent['info']['name']
        cat = c.calculateCategory(torrent, name)
        fporn = (cat == ['xxx'])
        total+= 1
        porn += int(isporn)
        if isporn == fporn:
            if DEBUG:
                print (isporn, fporn), 'good', name

        elif isporn and not fporn:
            fn+=1
            print 'FALSE NEGATIVE'
            showTorrent(os.path.join(torrentpath,tfilename))
        elif not isporn and fporn:
            fp +=1
            print 'FALSE POSITIVE'
            showTorrent(os.path.join(torrentpath,tfilename))

    print """
    Total torrents:   %(total)d
    XXX torrents:     %(porn)d
    Correct filtered: %(good)d
    False negatives:  %(fn)d
    False positives:  %(fp)d
    """ % {'total':total, 'porn':porn, 'fn':fn,'fp':fp,'good':total-fn-fp}

def readCategorisationFile(filename):
    global tdict
    tdict = {}
    try:
        f = file(filename, 'r')
        lines = f.read().splitlines()
        for line in lines:
            if line:
                parts = line.split('\t')
                tdict[parts[0]] = bool(int(parts[1]))
        f.close()
    except IOError:
        print 'No file %s found, starting with empty file' % filename

def getTorrentData(path, max_num=-1):
    torrents= []
    i = 0
    for fname in os.listdir(path):
        if fname.endswith('.torrent'):
            torrents.append(os.path.join(path,fname))
        if i%1000 == 0 and i:
            print 'Loaded: %d torrents' % i
        if i == int(max_num):
            break
        i+=1
    print 'Loaded %d torrents' % len(torrents)
    return torrents

def showTorrent(path):
    torrent = getMetainfo(os.path.join(path))
    name = torrent['info']['name']
    print '------------------------------'
    print '\tfiles  :'
    files_list = []
    __size_change = 1024
    try:
        # the multi-files mode
        for ifiles in torrent['info']["files"]:
            files_list.append((ifiles['path'][-1], ifiles['length'] / float(__size_change)))
    except KeyError:
        # single mode
        files_list.append((torrent['info']["name"],torrent['info']['length'] / float(__size_change)))
    for fname, fsize in files_list:
        print'\t\t%s\t%d kb' % (fname, fsize)
    print 'Torrent name: %s' % name
    print '\ttracker:%s' % torrent['announce']
    print '------------------------------'

def createTorrentDataSet(filename, torrentpath):
    initSaveFile(filename)
    f_out = file(filename, 'a')
    torrents = getTorrentData(torrentpath)
    for torrent in torrents:
        if os.path.split(torrent)[-1] in tset: # already done
            continue
        showTorrent(torrent)
        ans = None
        while ans not in ['q', 'y','n']:
            print 'Is this torrent porn? (y/n/q)'
            ans = sys.stdin.readline()[:-1].lower()
        if ans == 'q':
            break
        else:
            saveTorrent(f_out, torrent, (ans=='y'))
    f_out.close()

def saveTorrent(f_out, torrent, boolean):
    if torrent in tset:
        return
    tfilename = os.path.split(torrent)[-1]
    assert tfilename
    f_out.write('%s\t%d\n' % (tfilename, int(boolean)))
    f_out.flush()
    tset.add(torrent)

def initSaveFile(filename):
    global tset
    tset = set()
    try:
        f = file(filename, 'r')
        lines = f.read().splitlines()
        for line in lines:
            tset.add(line.split('\t')[0])
        f.close()
    except IOError:
        print 'No file %s found, starting with empty file' % filename



def main(args):
    if len(args) != 4 or args[1] not in ['categorise', 'test']:
        print 'Usage 1: %s categorise [torrent-dir] [torrent-data-file]' % args[0]
        print 'Usage 2: %s test [torrent-dir] [torrent-data-file]' % args[0]
        sys.exit(1)
    if args[1] == 'categorise':
        createTorrentDataSet(args[3], args[2])
    elif args[1] == 'test':
        testFilter(args[3], args[2])
    print 'ready'


if __name__ == '__main__':
    main(sys.argv)
