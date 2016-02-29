import json
from twisted.web import server
from twisted.web import resource
from Tribler.Core.simpledefs import NTFY_FREE_SPACE, NTFY_INSERT, NTFY_CHANNELCAST


class TriblerAPI(resource.Resource):

    '''
    This class implements an HTTP API that can be used by external processes to control the Tribler Core.
    Events in libtribler can be captured by performing a GET request to /events. This will open a HTTP connection
    where all important events are returned over in JSON format.
    '''

    def __init__(self, session):
        # Initialize the TriblerAPI, create the child resources and attach important observers.
        resource.Resource.__init__(self)
        self.session = session

        self.event_request_handler = EventRequestHandler()
        self.putChild("events", self.event_request_handler)

        self.channel_request_handler = ChannelRequestHandler(self.session)
        self.putChild("channel", self.channel_request_handler)

        # Add all observers for the api
        self.session.add_observer(self.event_request_handler.on_free_space, NTFY_FREE_SPACE, [NTFY_INSERT])


class ChannelRequestHandler(resource.Resource):

    def __init__(self, session):
        resource.Resource.__init__(self)

        self.channel_search_request_handler = ChannelSearchRequestHandler(session)
        self.putChild("search", self.channel_search_request_handler)


class ChannelSearchRequestHandler(resource.Resource):

    isLeaf = True

    def __init__(self, session):
        resource.Resource.__init__(self)
        self.session = session
        self.channel_db_handler = self.session.open_dbhandler(NTFY_CHANNELCAST)

    def render_GET(self, request):
        # TODO martijn: better error checking (parameters available? If not -> return 500?)
        # TODO martijn: this only performs a local search
        # TODO martijn: maybe use an object model here?
        results_local_channels = self.channel_db_handler.searchChannels(request.args['q'])

        results_json = []
        for channel_result in results_local_channels:
            print channel_result
            results_json.append({"name": channel_result[2]})

        response = {"channels": results_json}
        return json.dumps(response)



class EventRequestHandler(resource.Resource):

    '''
    The EventRequestHandler class is responsible for creating and posting events that happen in libtribler.
    '''

    isLeaf = True

    def __init__(self):
        resource.Resource.__init__(self)
        self.event_request = None

    def render_GET(self, request):
        self.event_request = request
        return server.NOT_DONE_YET

    def on_free_space(self, subject, change_type, object_id, free_space):
        if self.event_request:
            event = {"type" : "free_space", "free_space" : str(free_space)}
            self.event_request.write(json.dumps(event))
