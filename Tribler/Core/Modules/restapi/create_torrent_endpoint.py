import base64
import json
import os

from aiohttp import web

from libtorrent import bdecode

from Tribler.Core.Config.download_config import DownloadConfig
from Tribler.Core.Modules.restapi.rest_endpoint import HTTP_BAD_REQUEST, RESTEndpoint, RESTResponse
from Tribler.Core.Modules.restapi.util import return_handled_exception
from Tribler.Core.TorrentDef import TorrentDef
from Tribler.Core.Utilities.unicode import ensure_unicode, recursive_bytes
from Tribler.Core.exceptions import DuplicateDownloadException


class CreateTorrentEndpoint(RESTEndpoint):
    """
    Create a torrent file from local files.
    See: http://www.bittorrent.org/beps/bep_0012.html
    """

    def setup_routes(self):
        self.app.add_routes([web.post('', self.create_torrent)])

    async def create_torrent(self, request):
        """
        .. http:post:: /createtorrent?download=(boolean: download)

        Create a torrent from local files and return it in base64 encoding.
        Description and trackers list are optional.
        This endpoint returns a 500 HTTP response if a source file does not exist.
        You can optionally pass a flag to start downloading the created torrent.

            **Example request**:

            .. sourcecode:: none

                curl -X POST http://localhost:8085/createtorrent
                        --data "files[]=path/to/file.txt
                        &files[]=path/to/another/file.mp4
                        &description=Video
                        &trackers[]=url_tracker1
                        &trackers[]=url_backup1
                        &trackers[]=url_backup2
                        &export_dir=something"

            **Example response**:

            .. sourcecode:: javascript

                {
                    "torrent": { base64 encoded torrent file }
                }

            :statuscode 500: if source files do not exist.
        """
        parameters = await request.post()
        params = {}

        if 'files' in parameters and parameters['files']:
            file_path_list = [ensure_unicode(f, 'utf-8') for f in parameters.getall('files')]
        else:
            return RESTResponse({"error": "files parameter missing"}, status=HTTP_BAD_REQUEST)

        if 'description' in parameters and parameters['description']:
            params['comment'] = parameters['description']

        if 'trackers' in parameters and parameters['trackers']:
            tracker_url_list = parameters['trackers']
            params['announce'] = tracker_url_list[0]
            params['announce-list'] = tracker_url_list

        name = 'unknown'
        if 'name' in parameters and parameters['name']:
            name = parameters['name']
            params['name'] = name

        export_dir = None
        if 'export_dir' in parameters and parameters['export_dir']:
            export_dir = parameters['export_dir']

        from Tribler.Core.version import version_id
        params['created by'] = '%s version: %s' % ('Tribler', version_id)

        params['nodes'] = False
        params['httpseeds'] = False
        params['encoding'] = False
        params['piece length'] = 0  # auto

        try:
            result = await self.session.create_torrent_file(file_path_list, recursive_bytes(params))
        except (IOError, UnicodeDecodeError, RuntimeError) as e:
            self._logger.exception(e)
            return return_handled_exception(request, e)

        metainfo_dict = bdecode(result['metainfo'])

        if export_dir and os.path.exists(export_dir):
            save_path = os.path.join(export_dir, "%s.torrent" % name)
            with open(save_path, "wb") as fd:
                fd.write(result['metainfo'])

        # Download this torrent if specified
        if 'download' in request.query and request.query['download'] and request.query['download'] == "1":
            download_config = DownloadConfig()
            download_config.set_dest_dir(result['base_path'] if len(file_path_list) == 1 else result['base_dir'])
            try:
                self.session.lm.ltmgr.start_download(
                    tdef=TorrentDef(metainfo=metainfo_dict), dconfig=download_config)
            except DuplicateDownloadException:
                self._logger.warning("The created torrent is already being downloaded.")

        return RESTResponse(json.dumps({"torrent": base64.b64encode(result['metainfo']).decode('utf-8')}))
