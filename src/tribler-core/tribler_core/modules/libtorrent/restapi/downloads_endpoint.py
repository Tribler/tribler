from asyncio import CancelledError, TimeoutError as AsyncTimeoutError, wait_for
from binascii import unhexlify
from contextlib import suppress
from urllib.parse import unquote_plus
from urllib.request import url2pathname

from aiohttp import web

from aiohttp_apispec import docs, json_schema

from ipv8.REST.schema import schema
from ipv8.messaging.anonymization.tunnel import CIRCUIT_ID_PORT

from libtorrent import bencode

from marshmallow.fields import Boolean, Float, Integer, List, String

from pony.orm import db_session

from tribler_common.simpledefs import DOWNLOAD, UPLOAD, dlstatus_strings

from tribler_core.exceptions import InvalidSignatureException
from tribler_core.modules.libtorrent.download_config import DownloadConfig
from tribler_core.modules.libtorrent.stream import STREAM_PAUSE_TIME, StreamChunk
from tribler_core.modules.metadata_store.serialization import CHANNEL_TORRENT
from tribler_core.modules.metadata_store.store import UNKNOWN_CHANNEL, UPDATED_OUR_VERSION
from tribler_core.restapi.rest_endpoint import (
    HTTP_BAD_REQUEST,
    HTTP_INTERNAL_SERVER_ERROR,
    HTTP_NOT_FOUND,
    RESTEndpoint,
    RESTResponse,
    RESTStreamResponse,
)
from tribler_core.restapi.util import return_handled_exception
from tribler_core.utilities.path_util import Path
from tribler_core.utilities.unicode import ensure_unicode, hexlify


def _safe_extended_peer_info(ext_peer_info):
    """
    Given a string describing peer info, return a json.dumps() safe representation.

    :param ext_peer_info: the string to convert to a dumpable format
    :return: the safe string
    """
    # First see if we can use this as-is
    if not ext_peer_info:
        return ''

    try:
        return ensure_unicode(ext_peer_info, "utf8")
    except UnicodeDecodeError:
        # We might have some special unicode characters in here
        return u''.join([chr(c) for c in ext_peer_info])


class DownloadsEndpoint(RESTEndpoint):
    """
    This endpoint is responsible for all requests regarding downloads. Examples include getting all downloads,
    starting, pausing and stopping downloads.
    """

    def __init__(self, *args, **kwargs):
        super(DownloadsEndpoint, self).__init__(*args, **kwargs)

        self.app.on_shutdown.append(self.on_shutdown)

    async def on_shutdown(self, _):
        pass

    def setup_routes(self):
        self.app.add_routes([web.get('', self.get_downloads),
                             web.put('', self.add_download),
                             web.delete('/{infohash}', self.delete_download),
                             web.patch('/{infohash}', self.update_download),
                             web.get('/{infohash}/torrent', self.get_torrent),
                             web.get('/{infohash}/files', self.get_files),
                             web.get('/{infohash}/stream/{fileindex}', self.stream, allow_head=False)])

    @staticmethod
    def return_404(request, message="this download does not exist"):
        """
        Returns a 404 response code if your channel has not been created.
        """
        return RESTResponse({"error": message}, status=HTTP_NOT_FOUND)

    @staticmethod
    def create_dconfig_from_params(parameters):
        """
        Create a download configuration based on some given parameters. Possible parameters are:
        - anon_hops: the number of hops for the anonymous download. 0 hops is equivalent to a plain download
        - safe_seeding: whether the seeding of the download should be anonymous or not (0 = off, 1 = on)
        - destination: the destination path of the torrent (where it is saved on disk)
        """
        download_config = DownloadConfig()

        anon_hops = parameters.get('anon_hops', 0)
        safe_seeding = bool(parameters.get('safe_seeding', 0))

        if anon_hops > 0 and not safe_seeding:
            return None, "Cannot set anonymous download without safe seeding enabled"

        if anon_hops > 0:
            download_config.set_hops(anon_hops)

        if safe_seeding:
            download_config.set_safe_seeding(True)

        if 'destination' in parameters:
            download_config.set_dest_dir(parameters['destination'])

        if 'selected_files' in parameters:
            download_config.set_selected_files(parameters['selected_files'])

        return download_config, None

    @staticmethod
    def get_files_info_json(download):
        """
        Return file information as JSON from a specified download.
        """
        files_json = []
        files_completion = dict((name, progress) for name, progress in download.get_state().get_files_completion())
        selected_files = download.config.get_selected_files()
        file_index = 0
        for fn, size in download.get_def().get_files_with_length():
            files_json.append({
                "index": file_index,
                "name": str(Path(fn)),
                "size": size,
                "included": (file_index in selected_files or not selected_files),
                "progress": files_completion.get(fn, 0.0)
            })
            file_index += 1
        return files_json

    @docs(
        tags=["Libtorrent"],
        summary="Return all downloads, both active and inactive",
        parameters=[{
            'in': 'query',
            'name': 'get_peers',
            'description': 'Flag indicating whether or not to include peers',
            'type': 'boolean',
            'required': False
        },
        {
            'in': 'query',
            'name': 'get_pieces',
            'description': 'Flag indicating whether or not to include pieces',
            'type': 'boolean',
            'required': False
        },
        {
            'in': 'query',
            'name': 'get_files',
            'description': 'Flag indicating whether or not to include files',
            'type': 'boolean',
            'required': False
        }],
        responses={
            200: {
                "schema": schema(DownloadsResponse={
                    'downloads': schema(Download={
                        'name': String,
                        'progress': Float,
                        'infohash': String,
                        'speed_down': Float,
                        'speed_up': Float,
                        'status': String,
                        'size': Integer,
                        'eta': Integer,
                        'num_peers': Integer,
                        'num_seeds': Integer,
                        'total_up': Integer,
                        'total_down': Integer,
                        'ratio': Float,
                        'files': String,
                        'trackers': String,
                        'hops': Integer,
                        'anon_download': Boolean,
                        'safe_seeding': Boolean,
                        'max_upload_speed': Integer,
                        'max_download_speed': Integer,
                        'destination': String,
                        'availability': Float,
                        'peers': String,
                        'total_pieces': Integer,
                        'vod_mode': Boolean,
                        'vod_prebuffering_progress': Float,
                        'vod_prebuffering_progress_consec': Float,
                        'error': String,
                        'time_added': Integer
                    })
                }),
            }
        },
        description="This endpoint returns all downloads in Tribler, both active and inactive. The progress "
                    "is a number ranging from 0 to 1, indicating the progress of the specific state (downloading, "
                    "checking etc). The download speeds have the unit bytes/sec. The size of the torrent is given "
                    "in bytes. The estimated time assumed is given in seconds.\n\n"
                    "Detailed information about peers and pieces is only requested when the get_peers and/or "
                    "get_pieces flag is set. Note that setting this flag has a negative impact on performance "
                    "and should only be used in situations where this data is required. "
    )
    async def get_downloads(self, request):
        get_peers = request.query.get('get_peers', '0') == '1'
        get_pieces = request.query.get('get_pieces', '0') == '1'
        get_files = request.query.get('get_files', '0') == '1'

        downloads_json = []
        downloads = self.session.dlmgr.get_downloads()
        for download in downloads:
            if download.hidden and not download.config.get_channel_download():
                # We still want to send channel downloads since they are displayed in the GUI
                continue
            state = download.get_state()
            tdef = download.get_def()

            # Create tracker information of the download
            tracker_info = []
            for url, url_info in download.get_tracker_status().items():
                tracker_info.append({"url": url, "peers": url_info[0], "status": url_info[1]})

            num_seeds, num_peers = state.get_num_seeds_peers()
            num_connected_seeds, num_connected_peers = download.get_num_connected_seeds_peers()

            if download.config.get_channel_download():
                download_name = self.session.mds.ChannelMetadata.get_channel_name_cached(
                    tdef.get_name_utf8(), tdef.get_infohash())
            else:
                download_name = self.session.mds.TorrentMetadata.get_torrent_title(tdef.get_infohash()) or \
                                tdef.get_name_utf8()

            download_json = {
                "name": download_name,
                "progress": state.get_progress(),
                "infohash": hexlify(tdef.get_infohash()),
                "speed_down": state.get_current_payload_speed(DOWNLOAD),
                "speed_up": state.get_current_payload_speed(UPLOAD),
                "status": dlstatus_strings[state.get_status()],
                "size": tdef.get_length(),
                "eta": state.get_eta(),
                "num_peers": num_peers,
                "num_seeds": num_seeds,
                "num_connected_peers": num_connected_peers,
                "num_connected_seeds": num_connected_seeds,
                "total_up": state.get_total_transferred(UPLOAD),
                "total_down": state.get_total_transferred(DOWNLOAD),
                "ratio": state.get_seeding_ratio(),
                "trackers": tracker_info,
                "hops": download.config.get_hops(),
                "anon_download": download.get_anon_mode(),
                "safe_seeding": download.config.get_safe_seeding(),
                # Maximum upload/download rates are set for entire sessions
                "max_upload_speed": self.session.config.get_libtorrent_max_upload_rate(),
                "max_download_speed": self.session.config.get_libtorrent_max_download_rate(),
                "destination": str(download.config.get_dest_dir()),
                "availability": state.get_availability(),
                "total_pieces": tdef.get_nr_pieces(),
                "vod_prebuffering_progress": download.stream.prebuffprogress,
                "vod_prebuffering_progress_consec": download.stream.prebuffprogress_consec,
                "vod_header_progress": download.stream.headerprogress,
                "vod_footer_progress": download.stream.footerprogress,
                "vod_mode": download.stream.enabled,
                "error": repr(state.get_error()) if state.get_error() else "",
                "time_added": download.config.get_time_added(),
                "channel_download": download.config.get_channel_download()
            }

            # Add peers information if requested
            if get_peers:
                peer_list = state.get_peerlist()
                for peer_info in peer_list:  # Remove have field since it is very large to transmit.
                    del peer_info['have']
                    if 'extended_version' in peer_info:
                        peer_info['extended_version'] = _safe_extended_peer_info(peer_info['extended_version'])
                    # Does this peer represent a hidden servicecs circuit?
                    if peer_info.get('port') == CIRCUIT_ID_PORT:
                        tc = self.session.tunnel_community
                        circuit_id = tc.ip_to_circuit_id(peer_info['ip'])
                        circuit = tc.circuits.get(circuit_id, None)
                        if circuit:
                            peer_info['circuit'] = circuit_id

                download_json["peers"] = peer_list

            # Add piece information if requested
            if get_pieces:
                download_json["pieces"] = download.get_pieces_base64().decode('utf-8')

            # Add files if requested
            if get_files:
                download_json["files"] = self.get_files_info_json(download)

            downloads_json.append(download_json)
        return RESTResponse({"downloads": downloads_json})

    @docs(
        tags=["Libtorrent"],
        summary="Start a download from a provided URI.",
        parameters=[{
            'in': 'query',
            'name': 'get_peers',
            'description': 'Flag indicating whether or not to include peers',
            'type': 'boolean',
            'required': False
        },
        {
            'in': 'query',
            'name': 'get_pieces',
            'description': 'Flag indicating whether or not to include pieces',
            'type': 'boolean',
            'required': False
        },
        {
            'in': 'query',
            'name': 'get_files',
            'description': 'Flag indicating whether or not to include files',
            'type': 'boolean',
            'required': False
        }],
        responses={
            200: {
                "schema": schema(AddDownloadResponse={"started": Boolean, "infohash": String}),
                'examples': {"started": True, "infohash": "4344503b7e797ebf31582327a5baae35b11bda01"}
            }
        },
    )
    @json_schema(schema(AddDownloadRequest={
        'anon_hops': (Integer, 'Number of hops for the anonymous download. No hops is equivalent to a plain download'),
        'safe_seeding': (Boolean, 'Whether the seeding of the download should be anonymous or not'),
        'destination': (String, 'the download destination path of the torrent'),
        'uri*': (String, 'The URI of the torrent file that should be downloaded. This URI can either represent a file '
                         'location, a magnet link or a HTTP(S) url.'),
    }))
    async def add_download(self, request):
        parameters = await request.json()
        if not parameters.get('uri'):
            return RESTResponse({"error": "uri parameter missing"}, status=HTTP_BAD_REQUEST)

        download_config, error = DownloadsEndpoint.create_dconfig_from_params(parameters)
        if error:
            return RESTResponse({"error": error}, status=HTTP_BAD_REQUEST)

        uri = parameters['uri']
        if uri.startswith("file:"):
            filename = url2pathname(uri[5:])
            if uri.endswith(".mdblob") or uri.endswith(".mdblob.lz4"):
                with db_session:
                    try:
                        results = self.session.mds.process_mdblob_file(filename)
                        if results:
                            node, status = results[0]
                            if (status == UNKNOWN_CHANNEL or
                                    (status == UPDATED_OUR_VERSION and node.metadata_type == CHANNEL_TORRENT)):
                                node.subscribed = True
                                return RESTResponse({"started": True, "infohash": hexlify(node.infohash)})
                        return RESTResponse({"error": "Could not import Tribler metadata file"})
                    except IOError:
                        return RESTResponse({"error": "Metadata file not found"}, status=HTTP_BAD_REQUEST)
                    except InvalidSignatureException:
                        return RESTResponse({"error": "Metadata has invalid signature"}, status=HTTP_BAD_REQUEST)
            else:
                download_uri = u"file:%s" % filename
        else:
            download_uri = unquote_plus(uri)

        try:
            download = await self.session.dlmgr.start_download_from_uri(download_uri, config=download_config)
        except Exception as e:
            return RESTResponse({"error": str(e)}, status=HTTP_INTERNAL_SERVER_ERROR)

        return RESTResponse({"started": True, "infohash": hexlify(download.get_def().get_infohash())})

    @docs(
        tags=["Libtorrent"],
        summary="Remove a specific download.",
        parameters=[{
            'in': 'path',
            'name': 'infohash',
            'description': 'Infohash of the download to remove',
            'type': 'string',
            'required': True
        }],
        responses={
            200: {
                "schema": schema(DeleteDownloadResponse={"removed": Boolean, "infohash": String}),
                'examples': {"removed": True, "infohash": "4344503b7e797ebf31582327a5baae35b11bda01"}
            }
        },
    )
    @json_schema(schema(RemoveDownloadRequest={
        'remove_data': (Boolean, 'Whether or not to remove the associated data'),
    }))
    async def delete_download(self, request):
        parameters = await request.json()
        if 'remove_data' not in parameters:
            return RESTResponse({"error": "remove_data parameter missing"}, status=HTTP_BAD_REQUEST)

        infohash = unhexlify(request.match_info['infohash'])
        download = self.session.dlmgr.get_download(infohash)
        if not download:
            return DownloadsEndpoint.return_404(request)

        try:
            await self.session.dlmgr.remove_download(download, remove_content=parameters['remove_data'])
        except Exception as e:
            self._logger.exception(e)
            return return_handled_exception(request, e)

        return RESTResponse({"removed": True, "infohash": hexlify(download.get_def().get_infohash())})

    @docs(
        tags=["Libtorrent"],
        summary="Update a specific download.",
        parameters=[{
            'in': 'path',
            'name': 'infohash',
            'description': 'Infohash of the download to update',
            'type': 'string',
            'required': True
        }],
        responses={
            200: {
                "schema": schema(UpdateDownloadResponse={"modified": Boolean, "infohash": String}),
                'examples': {"modified": True, "infohash": "4344503b7e797ebf31582327a5baae35b11bda01"}
            }
        },
    )
    @json_schema(schema(UpdateDownloadRequest={
        'state': (String, 'State parameter to be passed to modify the state of the download (resume/stop/recheck)'),
        'selected_files': (List(Integer), 'File indexes to be included in the download'),
        'anon_hops': (Integer, 'The anonymity of a download can be changed at runtime by passing the anon_hops '
                               'parameter, however, this must be the only parameter in this request.')
    }))
    async def update_download(self, request):
        infohash = unhexlify(request.match_info['infohash'])
        download = self.session.dlmgr.get_download(infohash)
        if not download:
            return DownloadsEndpoint.return_404(request)

        parameters = await request.json()
        vod_mode = parameters.get("vod_mode")
        if vod_mode is not None:
            if not isinstance(vod_mode, bool):
                return RESTResponse({"error": "vod_mode must be bool flag"},
                                    status=HTTP_BAD_REQUEST)
            file_index = 0
            modified = False
            if vod_mode:
                file_index = parameters.get("fileindex")
                if file_index is None:
                    return RESTResponse({"error": "fileindex is necessary to enable vod_mode"},
                                        status=HTTP_BAD_REQUEST)
                if not download.stream.enabled or download.stream.fileindex != file_index:
                    await wait_for(download.stream.enable(file_index, request.http_range.start or 0), 10)
                    await download.stream.updateprios()
                    modified = True
            elif not vod_mode and download.stream.enabled:
                download.stream.disable()
                modified = True
            return RESTResponse({"vod_prebuffering_progress": download.stream.prebuffprogress,
                                 "vod_prebuffering_progress_consec": download.stream.prebuffprogress_consec,
                                 "vod_header_progress": download.stream.headerprogress,
                                 "vod_footer_progress": download.stream.footerprogress,
                                 "vod_mode": download.stream.enabled,
                                 "infohash": hexlify(download.get_def().get_infohash()),
                                 "modified": modified,
                                 })

        if len(parameters) > 1 and 'anon_hops' in parameters:
            return RESTResponse({"error": "anon_hops must be the only parameter in this request"},
                                status=HTTP_BAD_REQUEST)
        elif 'anon_hops' in parameters:
            anon_hops = int(parameters['anon_hops'])
            try:
                await self.session.dlmgr.update_hops(download, anon_hops)
            except Exception as e:
                self._logger.exception(e)
                return return_handled_exception(request, e)
            return RESTResponse({"modified": True, "infohash": hexlify(download.get_def().get_infohash())})

        if 'selected_files' in parameters:
            selected_files_list = parameters['selected_files']
            num_files = len(download.tdef.get_files())
            if not all([0 <= index < num_files for index in selected_files_list]):
                return RESTResponse({"error": "index out of range"}, status=HTTP_BAD_REQUEST)
            download.set_selected_files(selected_files_list)

        if parameters.get('state'):
            state = parameters['state']
            if state == "resume":
                download.resume()
            elif state == "stop":
                await download.stop(user_stopped=True)
            elif state == "recheck":
                download.force_recheck()
            elif state == "move_storage":
                dest_dir = Path(parameters['dest_dir'])
                if not dest_dir.exists():
                    return RESTResponse({"error": "Target directory (%s) does not exist" % dest_dir})
                download.move_storage(dest_dir)
                download.checkpoint()
            else:
                return RESTResponse({"error": "unknown state parameter"}, status=HTTP_BAD_REQUEST)

        return RESTResponse({"modified": True, "infohash": hexlify(download.get_def().get_infohash())})

    @docs(
        tags=["Libtorrent"],
        summary="Return the .torrent file associated with the specified download.",
        parameters=[{
            'in': 'path',
            'name': 'infohash',
            'description': 'Infohash of the download from which to get the .torrent file',
            'type': 'string',
            'required': True
        }],
        responses={
            200: {'description': 'The torrent'}
        }
    )
    async def get_torrent(self, request):
        infohash = unhexlify(request.match_info['infohash'])
        download = self.session.dlmgr.get_download(infohash)
        if not download:
            return DownloadsEndpoint.return_404(request)

        torrent = download.get_torrent_data()
        if not torrent:
            return DownloadsEndpoint.return_404(request)

        return RESTResponse(bencode(torrent), headers={'content-type': 'application/x-bittorrent',
                                                       'Content-Disposition': 'attachment; filename=%s.torrent'
                                                                              % hexlify(infohash).encode('utf-8')})

    @docs(
        tags=["Libtorrent"],
        summary="Return file information of a specific download.",
        parameters=[{
            'in': 'path',
            'name': 'infohash',
            'description': 'Infohash of the download to from which to get file information',
            'type': 'string',
            'required': True
        }],
        responses={
            200: {
                "schema": schema(GetFilesResponse={"files": [schema(File={'index': Integer,
                                                                          'name': String,
                                                                          'size': Integer,
                                                                          'included': Boolean,
                                                                          'progress': Float})]})
            }
        }
    )
    async def get_files(self, request):
        infohash = unhexlify(request.match_info['infohash'])
        download = self.session.dlmgr.get_download(infohash)
        if not download:
            return DownloadsEndpoint.return_404(request)
        return RESTResponse({"files": self.get_files_info_json(download)})

    @docs(
        tags=["Libtorrent"],
        summary="Stream the contents of a file that is being downloaded.",
        parameters=[{
            'in': 'path',
            'name': 'infohash',
            'description': 'Infohash of the download to stream',
            'type': 'string',
            'required': True
        },
        {
            'in': 'path',
            'name': 'fileindex',
            'description': 'The fileindex to stream',
            'type': 'string',
            'required': True
        }],
        responses={
            206: {'description': 'Contents of the stream'}
        }
    )
    async def stream(self, request):
        infohash = unhexlify(request.match_info['infohash'])
        download = self.session.dlmgr.get_download(infohash)
        if not download:
            return DownloadsEndpoint.return_404(request)

        file_index = int(request.match_info['fileindex'])

        http_range = request.http_range
        start = http_range.start or 0

        await wait_for(download.stream.enable(file_index, None if start > 0 else 0), 10)

        stop = download.stream.filesize if http_range.stop is None else min(http_range.stop, download.stream.filesize)

        if not start < stop or not 0 <= start < download.stream.filesize or not 0 < stop <= download.stream.filesize:
            return RESTResponse('Requested Range Not Satisfiable', status=416)

        response = RESTStreamResponse(status=206,
                                      reason='OK',
                                      headers={'Accept-Ranges': 'bytes',
                                               'Content-Type': 'application/octet-stream',
                                               'Content-Length': f'{stop - start}',
                                               'Content-Range': f'{start}-{stop}/{download.stream.filesize}'})
        response.force_close()
        with suppress(CancelledError, ConnectionResetError):
            async with StreamChunk(download.stream, start) as chunk:
                await response.prepare(request)
                bytes_todo = stop - start
                bytes_done = 0
                self._logger.info('Got range request for %s-%s (%s bytes)', start, stop, bytes_todo)
                while not request.transport.is_closing():
                    if chunk.seekpos >= download.stream.filesize:
                        break
                    data = await chunk.read()
                    try:
                        if len(data) == 0:
                            break
                        if bytes_done + len(data) > bytes_todo:
                            # if we have more data than we need
                            endlen = bytes_todo - bytes_done
                            if endlen != 0:
                                await wait_for(response.write(data[:endlen]), STREAM_PAUSE_TIME)

                                bytes_done += endlen
                            break
                        await wait_for(response.write(data), STREAM_PAUSE_TIME)
                        bytes_done += len(data)

                        if chunk.resume():
                            self._logger.debug("Stream %s-%s is resumed, starting sequential buffer", start, stop)
                    except AsyncTimeoutError:
                        # This means that stream writer has a full buffer, in practice means that
                        # the client keeps the conenction but sets the window size to 0. In this case
                        # there is no need to keep sequenial buffer if there are other chunks waiting for prios
                        if chunk.pause():
                            self._logger.debug("Stream %s-%s is paused, stopping sequential buffer", start, stop)
                return response
