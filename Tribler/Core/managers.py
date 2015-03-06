import os
import logging

from Tribler.dispersy.taskmanager import TaskManager
from Tribler.dispersy.util import blocking_call_on_reactor_thread, call_on_reactor_thread

from Tribler.community.search.community import SearchCommunity

from Tribler.Core.simpledefs import (SIGNAL_SEARCH_COMMUNITY, SIGNAL_ON_SEARCH_RESULTS, NTFY_CHANNELCAST, NTFY_MISC,
                                     SIGNAL_TORRENT)
from Tribler.Core.Search.SearchManager import split_into_keywords


class TorrentSearchManager(TaskManager):

    def __init__(self, session):
        super(TorrentSearchManager, self).__init__()
        self._logger = logging.getLogger(self.__class__.__name__)
        self.session = session
        self.dispersy = None
        self.channelcast_db = None
        self.misc_db = None

        self._current_keywords = None

    def initialize(self):
        self.dispersy = self.session.lm.dispersy
        self.channelcast_db = self.session.open_dbhandler(NTFY_CHANNELCAST)
        self.misc_db = self.session.open_dbhandler(NTFY_MISC)

        self.session.add_observer(self._on_search_results, SIGNAL_SEARCH_COMMUNITY, [SIGNAL_ON_SEARCH_RESULTS])

    @blocking_call_on_reactor_thread
    def shutdown(self):
        self.cancel_all_pending_tasks()
        self.channelcast_db = None
        self.misc_db = None
        self.dispersy = None
        self.session = None

    @call_on_reactor_thread
    def search(self, keywords):
        """
        Searches for torrents using SearchCommunity with the given keywords.
        :param keywords: The given keywords.
        """
        nr_requests_made = 0
        if self.dispersy is None:
            return nr_requests_made

        for community in self.dispersy.get_communities():
            if isinstance(community, SearchCommunity):
                self._current_keywords = keywords
                nr_requests_made = community.create_search(keywords)
                if not nr_requests_made:
                    self._logger.warn("Could not send search in SearchCommunity, no verified candidates found")

        return nr_requests_made

    @call_on_reactor_thread
    def _on_search_results(self, subject, change_type, object_id, search_results):
        """
        The callback function handles the search results.
        :param subject: Must be SIGNAL_SEARCH_COMMUNITY.
        :param change_type: Must be SIGNAL_ON_SEARCH_RESULTS.
        :param object_id: Must be None.
        :param search_results: The result dictionary which has 'keywords', 'results', and 'candidate'.
        """
        keywords = search_results['keywords']
        results = search_results['results']
        candidate = search_results['candidate']

        self._logger.debug("Got torrent search results %s, keywords %s, candidate %s",
                           len(results), keywords, candidate)

        # drop it if these are the results of an old keyword
        if keywords != self._current_keywords:
            return

        # results is a list of tuples that are:
        # (1) infohash, (2) name, (3) length, (4) num_files, (5) category_id, (6) creation_date, (7) num_seeders
        # (8) num_leechers, (9) channel_cid

        remote_torrent_result_list = []

        # get and cache channels
        channel_cid_list = [result[-1] for result in results if result[-1] is not None]
        channel_cache_list = self.channelcast_db.getChannelsByCID(channel_cid_list)
        channel_cache_dict = {}
        for channel in channel_cache_list:
            # index 1 is cid
            channel_cache_dict[channel[1]] = channel

        # create result dictionaries that are understandable
        for result in results:
            categories = result[4]
            category_id = self.misc_db.categoryName2Id(categories)

            remote_torrent_result = {'torrent_type': 'remote',  # indicates if it is a remote torrent
                                     'relevance_score': None,
                                     'torrent_id': -1,
                                     'infohash': result[0],
                                     'name': result[1],
                                     'length': result[2],
                                     'num_files': result[3],
                                     'category_id': category_id,
                                     'creation_date': result[5],
                                     'num_seeders': result[6],
                                     'num_leechers': result[7],
                                     'status_id': self.misc_db.torrentStatusName2Id(u'good'),
                                     'query_candidates': {candidate},
                                     'channel': None}

            channel_cid = result[-1]
            if channel_cid is not None and channel_cid in channel_cache_dict:
                channel = channel_cache_dict[channel_cid]
                channel_result = {'id': channel[0],
                                  'name': channel[2],
                                  'description': channel[3],
                                  'dispersy_cid': channel[1],
                                  'num_torrents': channel[4],
                                  'num_favorite': channel[5],
                                  'num_spam': channel[6],
                                  'modified': channel[8],
                                  }
                remote_torrent_result['channel'] = channel_result

            # guess matches
            keyword_set = set(keywords)
            swarmname_set = set(split_into_keywords(remote_torrent_result['name']))
            matches = {'fileextensions': set(),
                       'swarmname': swarmname_set & keyword_set,  # all keywords matching in swarmname
                       }
            matches['filenames'] = keyword_set - matches['swarmname']  # remaining keywords should thus me matching in filenames or fileextensions

            if len(matches['filenames']) == 0:
                _, ext = os.path.splitext(result[0])
                ext = ext[1:]

                matches['filenames'] = matches['swarmname']
                matches['filenames'].discard(ext)

                if ext in keyword_set:
                    matches['fileextensions'].add(ext)

            # Find the lowest term position of the matching keywords
            pos_score = None
            if matches['swarmname']:
                swarmnameTerms = split_into_keywords(remote_torrent_result['name'])
                swarmnameMatches = matches['swarmname']

                for i, term in enumerate(swarmnameTerms):
                    if term in swarmnameMatches:
                        pos_score = -i
                        break

            remote_torrent_result['relevance_score'] = [len(matches['swarmname']),
                                                        pos_score,
                                                        len(matches['filenames']),
                                                        len(matches['fileextensions']),
                                                        0]

            # append the result into the result list
            remote_torrent_result_list.append(remote_torrent_result)

        results_data = {'keywords': keywords,
                        'result_list': remote_torrent_result_list}
        # inform other components about the results
        self.session.uch.notify(SIGNAL_TORRENT, SIGNAL_ON_SEARCH_RESULTS, None, results_data)
