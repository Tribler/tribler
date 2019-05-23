import os

from twisted.web import resource
from twisted.web.static import File

import Tribler.Test.GUI.FakeTriblerAPI


class VideoRootEndpoint(resource.Resource):

    def getChild(self, path, request):
        return VideoEndpoint(path)


class VideoEndpoint(resource.Resource):

    def __init__(self, infohash):
        resource.Resource.__init__(self)
        self.infohash = infohash

    def getChild(self, path, request):
        return File(os.path.join(os.path.dirname(Tribler.Test.GUI.FakeTriblerAPI.__file__), "data", "video.avi"))
