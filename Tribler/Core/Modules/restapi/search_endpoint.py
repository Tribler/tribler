from __future__ import absolute_import
import logging
from binascii import unhexlify

from pony.orm import db_session, desc, select
from twisted.web import http, resource

import Tribler.Core.Utilities.json_util as json
from Tribler.Core.Modules.MetadataStore.serialization import CHANNEL_TORRENT, REGULAR_TORRENT
from Tribler.Core.Modules.restapi.util import convert_torrent_metadata_to_tuple, convert_db_torrent_to_json, \
    channel_to_torrent_adapter
from Tribler.Core.simpledefs import NTFY_CHANNELCAST, NTFY_TORRENTS

metadata_type_conversion_dict = {u'channel': CHANNEL_TORRENT,
                                 u'torrent': REGULAR_TORRENT}


def shift_and_clamp(x, s):
    return x - s if x > s else 0


json2pony_columns = {u'category': "tags",
                     u'id': "rowid",
                     u'name': "title",
                     u'size': "size",
                     u'infohash': "infohash",
                     u'date': "torrent_date",
                     u'commit_status': 'status'}


class SearchEndpoint(resource.Resource):
    """
    This endpoint is responsible for searching in channels and torrents present in the local Tribler database. It also
    fires a remote search in the Dispersy communities.
    """

    def __init__(self, session):
        resource.Resource.__init__(self)
        self.session = session
        self.events_endpoint = None
        self.channel_db_handler = self.session.open_dbhandler(NTFY_CHANNELCAST)
        self.torrent_db_handler = self.session.open_dbhandler(NTFY_TORRENTS)
        self._logger = logging.getLogger(self.__class__.__name__)

        self.putChild("completions", SearchCompletionsEndpoint(session))

    def render_GET(self, request):
        """
        .. http:get:: /search?q=(string:query)

        A GET request to this endpoint will create a search.

        first and last options limit the range of the query.
        xxx_filter option disables xxx filter
        channel option limits search to a certain channel
        sort_by option sorts results in forward or backward, based on column name (e.g. "id" vs "-id")
        txt option uses FTS search on the chosen word* terms
        type option limits query to certain metadata types (e.g. "torrent" or "channel")
        subscribed option limits query to channels you are subscribed for

            **Example request**:

            .. sourcecode:: none

                curl -X GET 'http://localhost:8085/search?txt=ubuntu&first=0&last=30&type=torrent&sort_by=size'

            **Example response**:

            .. sourcecode:: javascript

                {
                   "torrents":[
                      {
                         "commit_status":1,
                         "num_leechers":0,
                         "date":"1539867830.0",
                         "relevance_score":0,
                         "id":21,
                         "size":923795456,
                         "category":"unknown",
                         "public_key":"4c69624e...",
                         "name":"ubuntu-18.10-live-server-amd64.iso",
                         "last_tracker_check":0,
                         "infohash":"8c4adbf9ebe66f1d804fb6a4fb9b74966c3ab609",
                         "num_seeders":0,
                         "type":"torrent"
                      },
                      ...
                   ],
                   "chant_dirty":false
                }

        """



        first = 0
        last = None
        item_type = None
        channel_id = None
        txt_search_query = None
        sort_forward = True
        sort_column = u'id'
        sort_by = None
        chant_dirty = False
        subscribed = None
        channel = None

        xxx_filter = self.session.config.get_family_filter_enabled()
        if 'xxx_filter' in request.args and request.args['xxx_filter'] > 0 \
                and request.args['xxx_filter'][0] == "1":
            xxx_filter = False

        if 'first' in request.args and request.args['first'] > 0:
            first = int(request.args['first'][0])

        if 'last' in request.args and request.args['last'] > 0:
            last = int(request.args['last'][0])

        if 'type' in request.args and request.args['type'] > 0:
            item_type = str(request.args['type'][0])

        if 'channel' in request.args and request.args['channel'] > 0:
            channel_id = unhexlify(request.args['channel'][0])

        if 'sort_by' in request.args and request.args['sort_by'] > 0:
            sort_by = request.args['sort_by'][0]
            if sort_by.startswith(u'-'):
                sort_forward = False
                sort_column = sort_by[1:]
            else:
                sort_forward = True
                sort_column = sort_by

        if 'txt' in request.args and request.args['txt'] > 0:
            txt_search_query = request.args['txt'][0]

        if 'subscribed' in request.args and request.args['subscribed'] > 0:
            subscribed = int(request.args['subscribed'][0])

        results = []
        is_dispersy_channel = (len(channel_id) != 74) if channel_id else False

        # ACHTUNG! In its current form, the endpoint is carefully _designed_ to mix legacy and Pony results
        # together correctly in regards to pagination! Befor sending results for a page, it considers the whole
        # query size for _both_ legacy and Pony DBs, and then places the results correctly (Pony first, legacy last).

        # Legacy query for channel contents
        if is_dispersy_channel:
            channels_list = self.channel_db_handler.getChannelsByCID([channel_id])
            channel_info = channels_list[0] if channels_list else None
            if channel_info is None:
                return json.dumps({"error": "Channel with given Dispersy ID is not found"})

            torrent_db_columns = ['Torrent.torrent_id', 'infohash', 'Torrent.name', 'length', 'Torrent.category',
                                  'num_seeders', 'num_leechers', 'last_tracker_check', 'ChannelTorrents.inserted']
            results = self.channel_db_handler.getTorrentsFromChannelId(channel_info[0], True, torrent_db_columns,
                                                                       first=first, last=last)
        else:
            with db_session:
                # Object class to query
                base_type = self.session.lm.mds.TorrentMetadata
                if item_type == u'channel' or subscribed:
                    base_type = self.session.lm.mds.ChannelMetadata

                # Achtung! For Pony magic to work, iteration variable name (e.g. 'g') should be the same everywhere !!!
                pony_query = select(g for g in base_type)

                # Add FTS search terms
                if txt_search_query:
                    pony_query = base_type.search_keyword(txt_search_query + "*", lim=1000)

                # Filter by channel id
                if channel_id:
                    channel = self.session.lm.mds.ChannelMetadata.get(public_key=channel_id)
                    chant_dirty = channel.dirty
                    if not channel:
                        return json.dumps({"error": "Channel with given public key is not found"})
                    pony_query = pony_query.where(public_key=channel.public_key, metadata_type=REGULAR_TORRENT)

                # Filter by metadata type
                if item_type:
                    if item_type not in metadata_type_conversion_dict:
                        return json.dumps({"error": "Unknown metadata type queried: " + item_type})
                    pony_query = pony_query.where(metadata_type=metadata_type_conversion_dict[item_type])

                # Filter subscribed/non-subscribed
                if subscribed is not None:
                    pony_query = pony_query.where(subscribed=bool(subscribed))

                pony_query_size = pony_query.count()
                # Sort the query
                if sort_by:
                    sort_expression = "g." + json2pony_columns[sort_column]
                    sort_expression = sort_expression if sort_forward else desc(sort_expression)
                    pony_query = pony_query.sort_by(sort_expression)

                pony_query_results = [convert_torrent_metadata_to_tuple(md) for md in pony_query[first:last]]
                results.extend(pony_query_results)

            # Legacy query for subscribed channels
            skip_dispersy = not txt_search_query or (channel and not is_dispersy_channel)
            if subscribed:
                skip_dispersy = True
                subscribed_channels_db = self.channel_db_handler.getMySubscribedChannels(include_dispersy=True)
                results.extend([channel_to_torrent_adapter(c) for c in subscribed_channels_db])

            previous_query_size = pony_query_size
            if not skip_dispersy:
                # Legacy query for channels
                if item_type not in metadata_type_conversion_dict or item_type == u'channel':
                    first2 = shift_and_clamp(first, previous_query_size)
                    last2 = shift_and_clamp(last, previous_query_size)
                    dispersy_channels = []
                    count = 0
                    if txt_search_query:
                        dispersy_channels = self.channel_db_handler.search_in_local_channels_db(txt_search_query,
                                                                                                first=first2,
                                                                                                last=last2)
                        count = self.channel_db_handler.search_in_local_channels_db(txt_search_query, count=True)[0][0]
                    elif not channel_id:
                        dispersy_channels = self.channel_db_handler.getAllChannels(first=first, last=last)
                        count = self.channel_db_handler.getAllChannelsCount()[0][0]
                    results.extend([channel_to_torrent_adapter(c) for c in dispersy_channels])
                    previous_query_size += count

                # Legacy query for torrents
                if (item_type not in metadata_type_conversion_dict or item_type == u'torrent') and not channel_id:
                    first3 = shift_and_clamp(first, previous_query_size)
                    last3 = shift_and_clamp(last, previous_query_size)
                    torrent_db_columns = ['T.torrent_id', 'infohash', 'T.name', 'length', 'category',
                                          'num_seeders', 'num_leechers', 'last_tracker_check']
                    dispersy_torrents = self.torrent_db_handler.search_in_local_torrents_db(txt_search_query,
                                                                                            keys=torrent_db_columns,
                                                                                            first=first3,
                                                                                            last=last3,
                                                                                            family_filter=xxx_filter)
                    results.extend(dispersy_torrents)

        results_json = [convert_db_torrent_to_json(t) for t in results]

        return json.dumps({"torrents": results_json, "chant_dirty": chant_dirty})


class SearchCompletionsEndpoint(resource.Resource):
    """
    This class is responsible for managing requests regarding the search completions terms of a query.
    """

    def __init__(self, session):
        resource.Resource.__init__(self)
        self.session = session
        self.torrent_db_handler = self.session.open_dbhandler(NTFY_TORRENTS)

    def render_GET(self, request):
        """
        .. http:get:: /search/completions?q=(string:query)

        A GET request to this endpoint will return autocompletion suggestions for the given query. For instance,
        when searching for "pioneer", this endpoint might return "pioneer one" if that torrent is present in the
        local database. This endpoint can be used to suggest terms to users while they type their search query.

            **Example request**:

            .. sourcecode:: none

                curl -X GET http://localhost:8085/search/completions?q=pioneer

            **Example response**:

            .. sourcecode:: javascript

                {
                    "completions": ["pioneer one", "pioneer movie"]
                }
        """
        if 'q' not in request.args:
            request.setResponseCode(http.BAD_REQUEST)
            return json.dumps({"error": "query parameter missing"})

        keywords = unicode(request.args['q'][0], 'utf-8').lower()
        results = self.torrent_db_handler.getAutoCompleteTerms(keywords, max_terms=5)
        results.extend(self.session.lm.mds.TorrentMetadata.get_auto_complete_terms(keywords, max_terms=5))
        return json.dumps({"completions": results})
