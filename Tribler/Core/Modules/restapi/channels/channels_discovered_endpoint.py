from pony.orm import db_session
from twisted.web import http

from Tribler.Core.Modules.restapi.channels.base_channels_endpoint import BaseChannelsEndpoint
from Tribler.Core.Modules.restapi.channels.channels_playlists_endpoint import ChannelsPlaylistsEndpoint
from Tribler.Core.Modules.restapi.channels.channels_rss_endpoint import ChannelsRssFeedsEndpoint, \
    ChannelsRecheckFeedsEndpoint
from Tribler.Core.Modules.restapi.channels.channels_torrents_endpoint import ChannelsTorrentsEndpoint
from Tribler.Core.Modules.restapi.util import convert_db_channel_to_json, convert_channel_metadata_to_tuple
from Tribler.Core.exceptions import DuplicateChannelNameError
import Tribler.Core.Utilities.json_util as json


class ChannelsDiscoveredEndpoint(BaseChannelsEndpoint):
    """
    This class is responsible for requests regarding the discovered channels.
    """
    def getChild(self, path, request):
        return ChannelsDiscoveredSpecificEndpoint(self.session, path)

    @db_session
    def render_GET(self, _):
        """
        .. http:get:: /channels/discovered

        A GET request to this endpoint returns all channels discovered in Tribler.

            **Example request**:

            .. sourcecode:: none

                curl -X GET http://localhost:8085/channels/discovered

            **Example response**:

            .. sourcecode:: javascript

                {
                    "channels": [{
                        "id": 3,
                        "dispersy_cid": "da69aaad39ccf468aba2ab9177d5f8d8160135e6",
                        "name": "My fancy channel",
                        "description": "A description of this fancy channel",
                        "subscribed": False,
                        "votes": 23,
                        "torrents": 3,
                        "spam": 5,
                        "modified": 14598395,
                        "can_edit": True
                    }, ...]
                }
        """
        all_channels_db = self.channel_db_handler.getAllChannels()

        if self.session.config.get_chant_enabled():
            chant_channels = list(self.session.lm.mds.ChannelMetadata.select())
            for chant_channel in chant_channels:
                all_channels_db.append(convert_channel_metadata_to_tuple(chant_channel))

        results_json = []
        for channel in all_channels_db:
            channel_json = convert_db_channel_to_json(channel)
            if self.session.config.get_family_filter_enabled() and \
                    self.session.lm.category.xxx_filter.isXXX(channel_json['name']):
                continue

            results_json.append(channel_json)

        return json.dumps({"channels": results_json})

    def render_PUT(self, request):
        """
        .. http:put:: /channels/discovered

        Create your own new channel. The passed mode and descriptions are optional.
        Valid modes include: 'open', 'semi-open' or 'closed'. By default, the mode of the new channel is 'closed'.

            **Example request**:

            .. sourcecode:: none

                curl -X PUT http://localhost:8085/channels/discovered
                --data "name=fancy name&description=fancy description&mode=open"

            **Example response**:

            .. sourcecode:: javascript

                {
                    "added": 23
                }

            :statuscode 500: if a channel with the specified name already exists.
        """
        parameters = http.parse_qs(request.content.read(), 1)

        if 'name' not in parameters or len(parameters['name']) == 0 or len(parameters['name'][0]) == 0:
            request.setResponseCode(http.BAD_REQUEST)
            return json.dumps({"error": "channel name cannot be empty"})

        if 'description' not in parameters or len(parameters['description']) == 0:
            description = u''
        else:
            description = unicode(parameters['description'][0], 'utf-8')

        if self.session.config.get_chant_channel_edit():
            my_key = self.session.trustchain_keypair
            my_channel_id = my_key.pub().key_to_bin()

            # Do not allow to add a channel twice
            if self.session.lm.mds.get_my_channel():
                request.setResponseCode(http.INTERNAL_SERVER_ERROR)
                return json.dumps({"error": "channel already exists"})

            title = unicode(parameters['name'][0], 'utf-8')
            self.session.lm.mds.ChannelMetadata.create_channel(title, description)
            return json.dumps({
                "added": str(my_channel_id).encode("hex"),
            })

        if 'mode' not in parameters or len(parameters['mode']) == 0:
            # By default, the mode of the new channel is closed.
            mode = u'closed'
        else:
            mode = unicode(parameters['mode'][0], 'utf-8')

        try:
            channel_id = self.session.create_channel(unicode(parameters['name'][0], 'utf-8'), description, mode)
        except DuplicateChannelNameError as ex:
            return BaseChannelsEndpoint.return_500(self, request, ex)

        return json.dumps({"added": channel_id})


class ChannelsDiscoveredSpecificEndpoint(BaseChannelsEndpoint):
    """
    This class is responsible for dispatching requests to perform operations in a specific discovered channel.
    """

    def __init__(self, session, cid):
        BaseChannelsEndpoint.__init__(self, session)
        self.cid = bytes(cid.decode('hex'))

        child_handler_dict = {"torrents": ChannelsTorrentsEndpoint, "rssfeeds": ChannelsRssFeedsEndpoint,
                              "playlists": ChannelsPlaylistsEndpoint, "recheckfeeds": ChannelsRecheckFeedsEndpoint,
                              "mdblob": ChannelsDiscoveredExportEndpoint}
        for path, child_cls in child_handler_dict.iteritems():
            self.putChild(path, child_cls(session, self.cid))

    def render_GET(self, request):
        """
        .. http:get:: /channels/discovered/(string: channelid)

        Return the name, description and identifier of a channel.

            **Example request**:

            .. sourcecode:: none

                curl -X GET http://localhost:8085/channels/discovered/4a9cfc7ca9d15617765f4151dd9fae94c8f3ba11

            **Example response**:

            .. sourcecode:: javascript

                {
                    "overview": {
                        "name": "My Tribler channel",
                        "description": "A great collection of open-source movies",
                        "identifier": "4a9cfc7ca9d15617765f4151dd9fae94c8f3ba11"
                    }
                }

            :statuscode 404: if your channel has not been created (yet).
        """
        channel_info = self.get_channel_from_db(self.cid)
        if channel_info is None:
            return ChannelsDiscoveredSpecificEndpoint.return_404(request)

        return json.dumps({'overview': {'identifier': channel_info[1].encode('hex'), 'name': channel_info[2],
                                        'description': channel_info[3]}})


class ChannelsDiscoveredExportEndpoint(BaseChannelsEndpoint):
    """
    This class is responsible for serving .mdblob file export requests for a specific channel.
    """

    def __init__(self, session, cid):
        BaseChannelsEndpoint.__init__(self, session)
        self.cid = cid
        self.is_chant_channel = (len(cid) == 74)

    def render_GET(self, request):
        """
        .. http:get:: /channels/discovered/(string: channelid)/mdblob

        Return the mdblob binary

            **Example request**:

            .. sourcecode:: none

                curl -X GET http://localhost:8085/channels/discovered/(string: channel_id)/mdblob

            **Example response**:

            The .mdblob file containing the serialized and signed metadata for the channelid.

            :statuscode 404: if channel with given channeld is not found.
        """
        with db_session:
            channel = self.session.lm.mds.ChannelMetadata.get_channel_with_id(self.cid)
            if not channel:
                return ChannelsDiscoveredSpecificEndpoint.return_404(request)
            else:
                mdblob = channel.serialized()

        request.setHeader(b'content-type', 'application/octet-stream')
        request.setHeader(b'Content-Disposition', 'attachment; filename=%s.mdblob' % self.cid.encode('hex'))
        return mdblob
