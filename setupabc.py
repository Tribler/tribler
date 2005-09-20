# setup.py
from distutils.core import setup
import py2exe

#try:
#    import psyco
#    psyco.log()
#    psyco.full()
#except:
#    print 'psyco not installed, proceeding as normal'

setup(
    name = "ABC",
    options = {"py2exe": {"packages": ["encodings"],
                          "optimize": 2}},
    data_files = [("ABC",["abc.exe.manifest", "abc.nsi", "icon_abc.ico", "torrenticon.ico", "LICENSE.txt", "readme.txt", "announce.lst"])],
    windows = [
        {
            "script" : "abc.py",
            "icon_resources" : [(1, "icon_abc.ico")]
        }
    ],
)
