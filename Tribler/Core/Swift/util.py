#
# Convert a .torrent to a swift multi-file spec
#
# Author: Arno Bakker
#

import sys
from Tribler.Core.Utilities.bencode import bdecode

MULTIFILE_PATHNAME = "META-INF-multifilespec.txt"


def torrent2swiftspec(metainfo):
    info = metainfo["info"]
    if metainfo["encoding"] != "UTF-8":
        cname = info["name"]
        pname = cname.decode(metainfo["encoding"])
        uname = pname.encode("UTF-8")
        if "files" in info:
            for fdict in info["files"]:
                pathlist = fdict["path"]
                npl = []
                for p in pathlist:
                    cname = p
                    pname = cname.decode(metainfo["encoding"])
                    uname = pname.encode("UTF-8")
                    npl.append(uname)
                fdict["path"] = npl

    parent = info["name"]

    filelist = []
    if "files" in info:
        for fdict in info["files"]:
            pathlist = fdict["path"]
            flen = fdict["length"]
            pathname = parent
            for p in pathlist:
                pathname += "/"
                pathname += p
            filelist.append((pathname, flen))
    else:
        filelist.append(info["name"], info["length"])
        print "WARNING: Torrent contains single file, better seed via swift directly"

    return filelist2swiftspec(filelist)


def filelist2swiftspec(filelist):
    # TODO: verify that this gives same sort as C++ CreateMultiSpec
    filelist.sort()

    specbody = ""
    totalsize = 0
    for pathname, flen in filelist:
        specbody += pathname + " " +str(flen)+"\n"
        totalsize += flen

    specsize = len(MULTIFILE_PATHNAME) + 1 +0+1+len(specbody)
    numstr = str(specsize)
    numstr2 = str(specsize + len(str(numstr)))
    if (len(numstr) == len(numstr2)):
        specsize += len(numstr)
    else:
        specsize += len(numstr) + (len(numstr2) -len(numstr))

    spec = MULTIFILE_PATHNAME + " " +str(specsize)+"\n"
    spec += specbody
    return spec


if __name__ == "__main__":
    f = open(sys.argv[1], "rb")
    bdata = f.read()
    f.close()
    metainfo = bdecode(bdata)

    spec = torrent2swiftspec(metainfo)

    f = open(sys.argv[1] + ".spec", "wb")
    f.write(spec)
    f.close()
