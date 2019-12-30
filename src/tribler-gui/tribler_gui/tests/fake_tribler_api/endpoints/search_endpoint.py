from random import Random

from aiohttp import web

from tribler_core.restapi.rest_endpoint import HTTP_BAD_REQUEST, RESTEndpoint, RESTResponse

import tribler_gui.tests.fake_tribler_api.tribler_utils as tribler_utils


class SearchEndpoint(RESTEndpoint):

    def setup_routes(self):
        self.app.add_routes([web.get('', self.search),
                             web.get('/completions', self.completions),
                             web.get('/count', self.count)])

    @staticmethod
    def sanitize_parameters(parameters):
        """
        Sanitize the parameters and check whether they exist
        """
        first = 1 if 'first' not in parameters else int(parameters['first'])  # TODO check integer!
        last = 50 if 'last' not in parameters else int(parameters['last'])  # TODO check integer!
        sort_by = None if 'sort_by' not in parameters else parameters['sort_by']  # TODO check integer!
        sort_asc = True if 'sort_desc' not in parameters else bool(int(parameters['sort_desc']))
        query_filter = None if 'filter' not in parameters else parameters['filter']
        md_type = None if 'type' not in parameters else parameters['type']

        return first, last, sort_by, sort_asc, md_type, query_filter

    def base_get(self, request):
        if 'filter' not in request.query:
            return RESTResponse({"error": "filter parameter missing"}, status=HTTP_BAD_REQUEST)

        first, last, sort_by, sort_asc, md_type, query = SearchEndpoint.sanitize_parameters(request.query)
        random = Random()
        random.seed(hash(query))

        num_channels = len(tribler_utils.tribler_data.channels)
        num_torrents = len(tribler_utils.tribler_data.torrents)
        picked_torrents = random.sample(list(range(0, num_torrents - 1)), random.randint(20, num_channels - 1))
        picked_channels = random.sample(list(range(0, num_channels - 1)), random.randint(5, min(20, num_channels - 1)))

        torrents_json = []
        for index in picked_torrents:
            torrent_json = tribler_utils.tribler_data.torrents[index].get_json()
            torrent_json['type'] = 'torrent'
            torrents_json.append(torrent_json)

        if sort_by:
            torrents_json.sort(key=lambda result: result[sort_by] if sort_by in result else None, reverse=not sort_asc)

        channels_json = []
        for index in picked_channels:
            channel_json = tribler_utils.tribler_data.channels[index].get_json()
            channel_json['type'] = 'channel'
            channels_json.append(channel_json)

        if sort_by and sort_by not in ['category', 'size']:
            channels_json.sort(key=lambda result: result[sort_by] if sort_by in result else None, reverse=not sort_asc)

        if not md_type:
            search_results = channels_json + torrents_json
        elif md_type == 'channel':
            search_results = channels_json
        elif md_type == 'torrent':
            search_results = torrents_json
        else:
            search_results = []

        return first, last, sort_by, sort_asc, search_results

    async def search(self, request):
        include_total = request.query.get('include_total', '')
        first, last, sort_by, sort_asc, search_results = self.base_get(request)
        result = {
            "results": search_results[first-1:last],
            "first": first,
            "last": last,
            "sort_by": sort_by,
            "sort_desc": sort_asc,
        }
        if include_total:
            result.update({"total": len(search_results)})
        return RESTResponse(result)

    async def count(self, request):
        _, _, _, _, search_results = self.base_get(request)
        return RESTResponse({"total": len(search_results)})

    async def completions(self, request):
        if 'q' not in request.query:
            return RESTResponse({"error": "q parameter missing"}, status=HTTP_BAD_REQUEST)

        return RESTResponse({"completions": ["tribler1", "tribler2", "tribler3", "tribler4", "tribler5"]})
