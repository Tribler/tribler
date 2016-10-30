import json
import base64
import logging

from twisted.web import http, resource
from twisted.web.server import NOT_DONE_YET

from Tribler.Core.Modules.restapi.util import return_handled_exception


class CreateTorrentEndpoint(resource.Resource):
    """
    Create a torrent file from local files.
    See: http://www.bittorrent.org/beps/bep_0012.html
    """

    def __init__(self, session):
        resource.Resource.__init__(self)
        self._logger = logging.getLogger(self.__class__.__name__)
        self.session = session

    def render_POST(self, request):
        """
        .. http:post:: /createtorrent

        Create a torrent from local files and return it in base64 encoding.
        Description and trackers list are optional.
        This endpoint returns a 500 HTTP response if a source file does not exist.

            **Example request**:

            .. sourcecode:: none

                curl -X POST http://localhost:8085/createtorrent
                        --data "files[]=path/to/file.txt
                        &files[]=path/to/another/file.mp4
                        &description=Video
                        &trackers[]=url_tracker1
                        &trackers[]=url_backup1
                        &trackers[]=url_backup2"

            **Example response**:

            .. sourcecode:: javascript

                {
                    "torrent": { base64 encoded torrent file }
                }

            :statuscode 500: if source files do not exist.
        """
        parameters = http.parse_qs(request.content.read(), 1)
        params = {}

        if 'files[]' in parameters and len(parameters['files[]']) > 0:
            file_path_list = parameters['files[]']
        else:
            request.setResponseCode(http.BAD_REQUEST)
            return json.dumps({"error": "files parameter missing"})

        if 'description' in parameters and len(parameters['description']) > 0:
            params['comment'] = parameters['description'][0].encode('utf-8')

        if 'trackers[]' in parameters and len(parameters['trackers[]']) > 0:
            tracker_url_list = parameters['trackers[]']
            params['announce'] = tracker_url_list[0]
            params['announce-list'] = tracker_url_list

        from Tribler.Core.version import version_id
        params['created by'] = '%s version: %s' % ('Tribler', version_id)

        params['nodes'] = False
        params['httpseeds'] = False
        params['encoding'] = False
        params['piece length'] = 0  # auto

        def _on_torrent_created(result):
            """
            Success callback
            :param result: from create_torrent_file
            """
            with open(result['torrent_file_path'], 'rb') as f:
                torrent_64 = base64.b64encode(f.read())
            request.write(json.dumps({"torrent": torrent_64}))
            request.finish()

        def _on_create_failure(failure):
            """
            Error callback
            :param failure: from create_torrent_file
            """
            failure.trap(IOError)
            self._logger.exception(failure.value)
            request.write(return_handled_exception(request, failure.value))
            request.finish()

        deferred = self.session.create_torrent_file(file_path_list, params)
        deferred.addCallback(_on_torrent_created)
        deferred.addErrback(_on_create_failure)
        return NOT_DONE_YET
