#
# Convert a .torrent to a swift multi-file spec
#
# Author: Arno Bakker
#

MULTIFILE_PATHNAME = "META-INF-multifilespec.txt"


def filelist2swiftspec(filelist):
    # TODO: verify that this gives same sort as C++ CreateMultiSpec
    filelist.sort()

    specbody = ""
    for pathname, flen in filelist:
        specbody += pathname + " " +str(flen)+"\n"

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
