from libtorrent import bencode
from twisted.internet import reactor
from twisted.internet.defer import maybeDeferred
from twisted.web import http, resource, server
from Tribler.Test.util.Tracker.TrackerInfo import TrackerInfo


class TrackerRootEndpoint(resource.Resource):
    """
    This class is the root endpoint for every HTTP tracker request and dispatches scrape requests to other nodes in
    the resource tree.
    """

    def __init__(self, session):
        resource.Resource.__init__(self)
        self.putChild("scrape", TrackerScrapeEndpoint(session))


class TrackerScrapeEndpoint(resource.Resource):
    """
    This class handles requests regarding scrape requests.
    """
    def __init__(self, session):
        resource.Resource.__init__(self)
        self.session = session

    def render_GET(self, request):
        """
        Return a bencoded dictionary with information about the queried infohashes.
        """
        if 'info_hash' not in request.args:
            request.setResponseCode(http.BAD_REQUEST)
            return "infohash argument missing"

        response_dict = {'files': {}}
        for infohash in request.args['info_hash']:
            if not self.session.tracker_info.has_info_about_infohash(infohash):
                request.setResponseCode(http.BAD_REQUEST)
                return "no info about infohash %s" % infohash.encode('hex')

            info_dict = self.session.tracker_info.get_info_about_infohash(infohash)
            response_dict['files'][infohash] = {'complete': info_dict['seeders'],
                                                'downloaded': info_dict['downloaded'],
                                                'incomplete': info_dict['leechers']}

        return bencode(response_dict)


class HTTPTracker(object):

    def __init__(self, port):
        super(HTTPTracker, self).__init__()
        self.listening_port = None
        self.site = None
        self.port = port
        self.tracker_info = TrackerInfo()

    def start(self):
        """
        Start the HTTP Tracker
        """
        self.site = reactor.listenTCP(self.port, server.Site(resource=TrackerRootEndpoint(self)))

    def stop(self):
        """
        Stop the HTTP Tracker, returns a deferred that fires when the server is closed.
        """
        return maybeDeferred(self.site.stopListening)
