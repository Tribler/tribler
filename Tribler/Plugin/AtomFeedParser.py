# Written by Arno Bakker
# see LICENSE.txt for license information
import sys
import time
import xml.etree.ElementTree as etree

from Tribler.Core.Search.KeywordSearch import KeywordSearch
from Tribler.Core.Utilities.timeouturlopen import urlOpenTimeout


class MetaFeedParser:

    """ Parse an Atom feed that has Atom feeds as entries """

    def __init__(self, metafeedurl):
        self.metafeedurl = metafeedurl
        self.tree = None

    def parse(self):
        self.feedurls = []
        stream = urlOpenTimeout(self.metafeedurl, 10)
        self.tree = etree.parse(stream)
        entries = self.tree.findall('{http://www.w3.org/2005/Atom}entry')
        for entry in entries:
            titleelement = entry.find('{http://www.w3.org/2005/Atom}title')
            linkelement = entry.find('{http://www.w3.org/2005/Atom}link')
            if linkelement is not None:
                if linkelement.attrib['type'] == 'application/atom+xml':
                    # Got feed
                    feedurl = linkelement.attrib['href']
                    self.feedurls.append(feedurl)

    def get_feedurls(self):
        return self.feedurls


class FeedParser:

    def __init__(self, feedurl):
        self.feedurl = feedurl
        self.tree = None

    def parse(self):
        self.title2entrymap = {}
        print >>sys.stderr, "feedp: Parsing", self.feedurl
        stream = urlOpenTimeout(self.feedurl, 10)
        self.tree = etree.parse(stream)
        entries = self.tree.findall('{http://www.w3.org/2005/Atom}entry')
        for entry in entries:
            titleelement = entry.find('{http://www.w3.org/2005/Atom}title')
            # print >> sys.stderr,"feedp: Got title",titleelement.text
            self.title2entrymap[titleelement.text] = entry

    def search(self, searchstr):
        """ Use Jelle's smart keyword search """
        needles = searchstr.strip().split(' ')

        haystack = []
        for title, entry in self.title2entrymap.iteritems():
            record = {}
            record['name'] = title
            record['entry'] = entry
            haystack.append(record)

        records = KeywordSearch().search(haystack, needles)
        hits = []
        for record in records:
            hits.append(record['entry'])
        return hits


def feedhits2atomxml(feedhits, searchstr, urlpathprefix):

    new_feed = etree.Element('{http://www.w3.org/2005/Atom}feed', attrib={'xmlns:rdf': "http://www.w3.org/1999/02/22-rdf-syntax-ns#", 'xmlns:sy': "http://purl.org/rss/1.0/modules/syndication/", 'xmlns:dc': "http://purl.org/dc/elements/1.1/", 'xmlns:p2pnext':"urn:p2pnext:contentfeed:2009", 'xmlns:taxo':"http://purl.org/rss/1.0/modules/taxonomy/"})

    title = etree.SubElement(new_feed, 'title')
    title.text = 'Hits for ' + searchstr

    link = etree.SubElement(new_feed, 'link', attrib={'rel': 'self', 'href': urlpathprefix})
    author = etree.SubElement(new_feed, 'author')
    name = etree.SubElement(author, 'name')
    name.text = 'NSSA'
    id = etree.SubElement(new_feed, 'id')
    id.text = 'urn:nssa'
    updated = etree.SubElement(new_feed, 'updated')
    updated.text = now2formatRFC3339()
    # TODO image = etree.SubElement(new_feed,'p2pnext:image',attrib={'src':"http://p2pnextfeed1.rad0.net/images/bbc.png"})

    for entry in feedhits:
        new_feed.append(entry)

    atom = '<?xml version="1.0" encoding="UTF-8"?>\n'
    atom += etree.tostring(new_feed)
    # Parser anomaly / formally correct bla bla
    atom = atom.replace(":ns0=", "=")
    atom = atom.replace("ns0:", "")
    return atom


def now2formatRFC3339():
    formatstr = "%Y-%m-%dT%H:%M:%S"
    s = time.strftime(formatstr, time.gmtime())
    s += 'Z'
    return s


if __name__ == '__main__':
    searchstr = "Episode"

    metafp = MetaFeedParser('http://p2pnextfeed1.rad0.net/content/feed/bbc')
    metafp.parse()

    allhits = []
    for feedurl in metafp.get_feedurls():
        feedp = FeedParser(feedurl)
        feedp.parse()
        hits = feedp.search(searchstr)
        allhits.extend(hits)

    # print >>sys.stderr,"Got hits",`hits`

    for hitentry in allhits:
        titleelement = hitentry.find('{http://www.w3.org/2005/Atom}title')
        print >>sys.stderr, "Got hit", titleelement.text

    atomxml = feedhits2atomxml(allhits, searchstr, "http://localhost/bla")
    print >>sys.stderr, "Result feed", atomxml
