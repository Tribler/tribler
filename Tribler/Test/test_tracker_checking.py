# Written by Yuan Yuan, Jie Yang
# see LICENSE.txt for license information

from Tribler.TrackerChecking.TorrentChecking import TorrentChecking
from time import sleep

def run():
    print "start run"
#    torrent_db = TorrentDBHandler.getInstance()
#    key = ['infohash', 'torrent_name', 'torrent_dir', 'relevance', 'info', 
#                'num_owners', 'leecher', 'seeder', 'category']
#    data = torrent_db.getRecommendedTorrents(key)
#
#    for idata in data[54:100]:
#        trackerChecking(idata)
    t = TorrentChecking(2)
    
run()