import json
import logging
import time
from twisted.web import http, resource
from Tribler.Core.simpledefs import NTFY_CHANNELCAST
from Tribler.community.allchannel.community import AllChannelCommunity
from Tribler.dispersy.exception import CommunityNotFoundException

UNKNOWN_CHANNEL_RESPONSE_MSG = "the channel with the provided cid is not known"
UNAUTHORIZED_RESPONSE_MSG = "you are not authorized to perform this request"


class BaseChannelsEndpoint(resource.Resource):
    """
    This class contains some utility methods to work with raw channels from the database.
    All endpoints that are using the database, should derive from this class.
    """

    def __init__(self, session):
        resource.Resource.__init__(self)
        self.session = session
        self.channel_db_handler = self.session.open_dbhandler(NTFY_CHANNELCAST)
        self._logger = logging.getLogger(self.__class__.__name__)

    @staticmethod
    def return_404(request, message=UNKNOWN_CHANNEL_RESPONSE_MSG):
        """
        Returns a 404 response code if your channel has not been created.
        """
        request.setResponseCode(http.NOT_FOUND)
        return json.dumps({"error": message})

    def return_500(self, request, exception):
        self._logger.exception(exception)
        request.setResponseCode(http.INTERNAL_SERVER_ERROR)
        return json.dumps({
            u"error": {
                u"handled": True,
                u"code": exception.__class__.__name__,
                u"message": exception.message
            }
        })

    @staticmethod
    def return_401(request, message=UNAUTHORIZED_RESPONSE_MSG):
        """
        Returns a 401 response code if you are not authorized to perform a specific request.
        """
        request.setResponseCode(http.UNAUTHORIZED)
        return json.dumps({"error": message})

    def get_channel_from_db(self, cid):
        """
        Returns information about the channel from the database. Returns None if the channel with given cid
        does not exist.
        """
        channels_list = self.channel_db_handler.getChannelsByCID([cid])
        return channels_list[0] if len(channels_list) > 0 else None

    def get_my_channel_object(self):
        """
        Returns the Channel object associated with a channel that is used to manage rss feeds.
        """
        my_channel_id = self.channel_db_handler.getMyChannelId()
        return self.session.lm.channel_manager.get_my_channel(my_channel_id)

    def vote_for_channel(self, cid, vote):
        """
        Make a vote in the channel specified by the cid. Returns a deferred that fires when the vote is done.
        """
        for community in self.session.get_dispersy_instance().get_communities():
            if isinstance(community, AllChannelCommunity):
                return community.disp_create_votecast(cid, vote, int(time.time()))

    def get_community_for_channel_id(self, channel_id):
        """
        Returns a Dispersy community from the given channel id. The Community object can be used to delete/add torrents
        or modify playlists in a specific channel.
        """
        dispersy_cid = str(self.channel_db_handler.getDispersyCIDFromChannelId(channel_id))
        try:
            return self.session.get_dispersy_instance().get_community(dispersy_cid)
        except CommunityNotFoundException:
            return None
