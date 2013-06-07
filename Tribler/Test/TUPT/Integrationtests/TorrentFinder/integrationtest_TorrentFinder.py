import time

from Tribler.Test.TUPT.test_StubPluginManager import PluginManagerStub

from Tribler.TUPT.TorrentFinder.TorrentFinderControl import TorrentFinderControl
from Tribler.TUPT.Movie import Movie

#Create a movie
movie = Movie()
movie.dictionary['title'] = 'TestMovie'
movie.dictionary['year'] = 2013
#Create a pluginmanager containing a forever looping plugin.
pluginManager = PluginManagerStub(loopTorrentFinder = True)
#Create the torrentFinderControl.
torrentFinderControl = TorrentFinderControl(pluginManager, movie)
#Look for new torrents.
torrentFinderControl.start()
#Kill all threads.
time.sleep(1)
#


