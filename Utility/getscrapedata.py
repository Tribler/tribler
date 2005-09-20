from sha import sha
import re
import binascii
import sys

from BitTornado.bencode import *

from threading import Thread
   
class ScrapeThread(Thread):
    def __init__(self, utility, ABCTorrent, name = None):
        Thread.__init__(self, None, None, name)
        self.ABCTorrent = ABCTorrent
        self.utility = utility

    def run(self):
        self.GetScrapeData()

    def GetScrapeData(self):
        status = self.utility.lang.get('scraping')
        currentseed = "?"
        currentpeer = "?"
        
        # connect scrape at tracker and get data
        # save at self.currentpeer, self.currentseed
        # if error put '?'

        # The thread itself will update the list for its scraping infos
        self.ABCTorrent.updateScrapeData(currentpeer, currentseed, status)
        
        metainfo = self.ABCTorrent.getResponse()

        if metainfo is None:
            status = self.utility.lang.get('cantreadmetainfo')
        else:            
            info = metainfo['info']
            info_hash = sha(bencode(info))

            announce = None            
            if metainfo.has_key('announce'):
                announce = metainfo['announce']
            elif metainfo.has_key('announce-list'):
                announce_list = metainfo['announce-list']
                announce = announce_list[0][0]
            
            if announce is not None:
                #sys.stdout.write('Announce URL: ' + announce + '\n');
                p = re.compile( '(.*/)[^/]+')
                surl = p.sub (r'\1', announce)
                #sys.stdout.write('sURL1: ' + surl + '\n')
                #Fix this to comply with scrape standards.
                ix = announce.rindex('/')
                #tmp = 'ix: '.join(ix)
                #sys.stdout.write('ix: ' + str(ix) + '\n')
                if (ix + 9) > len(announce):
                    ix2 = len(announce)
                else:
                    ix2 = ix + 9
                #sys.stdout.write('ix: ' + announce[(ix + 1):(ix2)] + '\n')
                if announce[(ix + 1):(ix2)].endswith("announce", 0):
                    #sys.stdout.write('!!!VALID SCRAPE URL!!!' + '\n')
                    #sys.stdout.write('sURLTrue: ' + surl + 'scrape' + announce[(ix2):] + '\n');
                    surl = surl + 'scrape' + announce[(ix2):] + '?info_hash='
                #end new Scrape URL Code
                info_hash_hex = info_hash.hexdigest()
                hashlen = len(info_hash_hex)
                for i in range(0, hashlen):
                    if (i % 2 == 0):
                        surl = surl + "%"
                    surl = surl + info_hash_hex[i]
                    
                # connect scrape URL
                scrapedata = self.utility.getMetainfo(surl, url = True)
                if scrapedata is None or not scrapedata.has_key('files'):
                    status = self.utility.lang.get('cantgetdatafromtracker')                        
                else:
                    scrapedata = scrapedata['files']
                    for i in scrapedata.keys():
                        if binascii.b2a_hex(i) == info_hash_hex:
                            currentpeer = str(scrapedata[i]['incomplete'])
                            currentseed = str(scrapedata[i]['complete'])
                            status = self.utility.lang.get('scrapingdone')
            else:
                status = self.utility.lang.get('noannouncetrackerinmeta')
        
        # The thread itself will update the list for its scraping infos
        self.ABCTorrent.updateScrapeData(currentpeer, currentseed, status)