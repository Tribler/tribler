import mimetypes
from asyncio import CancelledError, sleep
from binascii import unhexlify
from contextlib import suppress
from urllib.parse import unquote_plus
from urllib.request import url2pathname

from aiohttp import web

from ipv8.messaging.anonymization.tunnel import CIRCUIT_ID_PORT

from libtorrent import bencode, create_torrent

from pony.orm import db_session

from tribler_common.simpledefs import DOWNLOAD, UPLOAD, dlstatus_strings

from tribler_core.exceptions import InvalidSignatureException
from tribler_core.modules.libtorrent.download_config import DownloadConfig
from tribler_core.modules.libtorrent.stream import Stream
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
from tribler_core.utilities.torrent_utils import get_info_from_handle
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
        self.streams = {}
        self.app.on_shutdown.append(self.on_shutdown)

    async def on_shutdown(self, _):
        for stream in self.streams.values():
            stream.close()
        self.streams.clear()

    def setup_routes(self):
        self.app.add_routes([web.get('', self.get_downloads),
                             web.put('', self.add_download),
                             web.delete('/{infohash}', self.delete_download),
                             web.patch('/{infohash}', self.update_download),
                             web.get('/{infohash}/torrent', self.get_torrent),
                             web.get('/{infohash}/files', self.get_files),
                             web.get('/{infohash}/stream/{fileindex}', self.stream)])

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

    async def get_downloads(self, request):
        """
        .. http:get:: /downloads?get_peers=(boolean: get_peers)&get_pieces=(boolean: get_pieces)

        A GET request to this endpoint returns all downloads in Tribler, both active and inactive. The progress is a
        number ranging from 0 to 1, indicating the progress of the specific state (downloading, checking etc). The
        download speeds have the unit bytes/sec. The size of the torrent is given in bytes. The estimated time assumed
        is given in seconds. A description of the possible download statuses can be found in the REST API documentation.

        Detailed information about peers and pieces is only requested when the get_peers and/or get_pieces flag is set.
        Note that setting this flag has a negative impact on performance and should only be used in situations
        where this data is required.

            **Example request**:

            .. sourcecode:: none

                curl -X GET http://localhost:8085/downloads?get_peers=1&get_pieces=1

            **Example response**:

            .. sourcecode:: javascript

                {
                    "downloads": [{
                        "name": "Ubuntu-16.04-desktop-amd64",
                        "progress": 0.31459265,
                        "infohash": "4344503b7e797ebf31582327a5baae35b11bda01",
                        "speed_down": 4938.83,
                        "speed_up": 321.84,
                        "status": "DLSTATUS_DOWNLOADING",
                        "size": 89432483,
                        "eta": 38493,
                        "num_peers": 53,
                        "num_seeds": 93,
                        "total_up": 10000,
                        "total_down": 100000,
                        "ratio": 0.1,
                        "files": [{
                            "index": 0,
                            "name": "ubuntu.iso",
                            "size": 89432483,
                            "included": True
                        }, ...],
                        "trackers": [{
                            "url": "http://ipv6.torrent.ubuntu.com:6969/announce",
                            "status": "Working",
                            "peers": 42
                        }, ...],
                        "hops": 1,
                        "anon_download": True,
                        "safe_seeding": True,
                        "max_upload_speed": 0,
                        "max_download_speed": 0,
                        "destination": "/home/user/file.txt",
                        "availability": 1.234,
                        "peers": [{
                            "ip": "123.456.789.987",
                            "dtotal": 23,
                            "downrate": 0,
                            "uinterested": False,
                            "optimistic": False,
                            ...
                        }, ...],
                        "total_pieces": 420,
                        "vod_mod": True,
                        "vod_prebuffering_progress": 0.89,
                        "vod_prebuffering_progress_consec": 0.86,
                        "error": "",
                        "time_added": 1484819242,
                    }
                }, ...]
        """
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
                "vod_prebuffering_progress": 0,
                "vod_prebuffering_progress_consec": 0,
                "error": repr(state.get_error()) if state.get_error() else "",
                "time_added": download.config.get_time_added(),
                "channel_download": download.config.get_channel_download()
            }

            stream = self.streams.get(tdef.get_infohash())
            download_json['vod_mode'] = stream is not None
            if stream:
                download_json.update(stream.get_progress())

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

    async def add_download(self, request):
        """
        .. http:put:: /downloads

        A PUT request to this endpoint will start a download from a provided URI. This URI can either represent a file
        location, a magnet link or a HTTP(S) url.
        - anon_hops: the number of hops for the anonymous download. 0 hops is equivalent to a plain download
        - safe_seeding: whether the seeding of the download should be anonymous or not (0 = off, 1 = on)
        - destination: the download destination path of the torrent
        - torrent: the URI of the torrent file that should be downloaded. This parameter is required.

            **Example request**:

                .. sourcecode:: none

                    curl -X PUT http://localhost:8085/downloads
                    --data "anon_hops=2&safe_seeding=1&destination=/my/dest/on/disk/&uri=file:/home/me/test.torrent

            **Example response**:

                .. sourcecode:: javascript

                    {"started": True, "infohash": "4344503b7e797ebf31582327a5baae35b11bda01"}
        """
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
            download = await self.session.dlmgr.start_download_from_uri(download_uri, download_config)
        except Exception as e:
            return RESTResponse({"error": str(e)}, status=HTTP_INTERNAL_SERVER_ERROR)

        return RESTResponse({"started": True, "infohash": hexlify(download.get_def().get_infohash())})

    async def delete_download(self, request):
        """
        .. http:delete:: /downloads/(string: infohash)

        A DELETE request to this endpoint removes a specific download from Tribler. You can specify whether you only
        want to remove the download or the download and the downloaded data using the remove_data parameter.

            **Example request**:

                .. sourcecode:: none

                    curl -X DELETE http://localhost:8085/download/4344503b7e797ebf31582327a5baae35b11bda01
                    --data "remove_data=1"

            **Example response**:

                .. sourcecode:: javascript

                    {"removed": True, "infohash": "4344503b7e797ebf31582327a5baae35b11bda01"}
        """
        parameters = await request.json()
        if 'remove_data' not in parameters:
            return RESTResponse({"error": "remove_data parameter missing"}, status=HTTP_BAD_REQUEST)

        infohash = unhexlify(request.match_info['infohash'])
        download = self.session.dlmgr.get_download(infohash)
        if not download:
            return DownloadsEndpoint.return_404(request)

        stream = self.streams.pop(infohash, None)
        if stream:
            stream.close()

        try:
            await self.session.dlmgr.remove_download(download, remove_content=parameters['remove_data'])
        except Exception as e:
            self._logger.exception(e)
            return return_handled_exception(request, e)

        return RESTResponse({"removed": True, "infohash": hexlify(download.get_def().get_infohash())})

    async def update_download(self, request):
        """
        .. http:patch:: /downloads/(string: infohash)

        A PATCH request to this endpoint will update a download in Tribler.

        A state parameter can be passed to modify the state of the download. Valid states are "resume"
        (to resume a stopped/paused download), "stop" (to stop a running download) and "recheck"
        (to force a recheck of the hashes of a download).

        Another possible parameter is selected_files which manipulates which files are included in the download.
        The selected_files parameter is an array with the file indices as values.

        The anonymity of a download can be changed at runtime by passing the anon_hops parameter, however, this must
        be the only parameter in this request.

            **Example request**:

                .. sourcecode:: none

                    curl -X PATCH http://localhost:8085/downloads/4344503b7e797ebf31582327a5baae35b11bda01
                    --data "state=resume&selected_files[]=file1.iso&selected_files[]=1"

            **Example response**:

                .. sourcecode:: javascript

                    {"modified": True, "infohash": "4344503b7e797ebf31582327a5baae35b11bda01"}
        """
        infohash = unhexlify(request.match_info['infohash'])
        download = self.session.dlmgr.get_download(infohash)
        if not download:
            return DownloadsEndpoint.return_404(request)

        parameters = await request.json()
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

    async def get_torrent(self, request):
        """
        .. http:get:: /download/(string: infohash)/torrent

        A GET request to this endpoint returns the .torrent file associated with the specified download.

            **Example request**:

                .. sourcecode:: none

                    curl -X GET http://localhost:8085/downloads/4344503b7e797ebf31582327a5baae35b11bda01/torrent

            **Example response**:

            The contents of the .torrent file.
        """
        infohash = unhexlify(request.match_info['infohash'])
        download = self.session.dlmgr.get_download(infohash)
        if not download:
            return DownloadsEndpoint.return_404(request)

        if not download.handle or not download.handle.is_valid() or not download.handle.has_metadata():
            return DownloadsEndpoint.return_404(request)

        torrent_info = get_info_from_handle(download.handle)
        t = create_torrent(torrent_info)
        torrent = t.generate()

        return RESTResponse(bencode(torrent), headers={'content-type': 'application/x-bittorrent',
                                                       'Content-Disposition': 'attachment; filename=%s.torrent'
                                                                              % hexlify(infohash).encode('utf-8')})

    async def get_files(self, request):
        """
        .. http:get:: /download/(string: infohash)/files

        A GET request to this endpoint returns the file information of a specific download.

            **Example request**:

                .. sourcecode:: none

                    curl -X GET http://localhost:8085/downloads/4344503b7e797ebf31582327a5baae35b11bda01/files

            **Example response**:

            .. sourcecode:: javascript

                {
                    "files": [{
                        "index": 1,
                        "name": "test.txt",
                        "size": 12345,
                        "included": True,
                        "progress": 0.5448
                    }, ...]
                }
        """
        infohash = unhexlify(request.match_info['infohash'])
        download = self.session.dlmgr.get_download(infohash)
        if not download:
            return DownloadsEndpoint.return_404(request)
        return RESTResponse({"files": self.get_files_info_json(download)})

    async def stream(self, request):
        infohash = unhexlify(request.match_info['infohash'])
        download = self.session.dlmgr.get_download(infohash)
        if not download:
            return DownloadsEndpoint.return_404(request)

        file_index = int(request.match_info['fileindex'])
        if not 0 <= file_index < len(download.get_def().get_files()):
            return RESTResponse('Selected file out of range', status=HTTP_NOT_FOUND)

        stream = self.streams.get(infohash)
        if stream and stream.file_index != file_index:
            stream.close()
        if not stream or stream.closed:
            stream = self.streams[infohash] = Stream(download, file_index)
        file_size = stream.file_size

        http_range = request.http_range
        start = http_range.start or 0
        stop = http_range.stop if http_range.stop is not None else file_size

        if not start < stop or not 0 <= start < file_size or not 0 < stop <= file_size:
            return RESTResponse('Requested Range Not Satisfiable', status=416)

        mime_type = mimetypes.guess_type(str(stream.filename))[0]
        response = RESTStreamResponse(status=206, reason='OK', headers={'Accept-Ranges': 'bytes',
                                                                        'Content-Type': mime_type or 'text/html',
                                                                        'Content-Length': f'{stop - start}',
                                                                        'Content-Range': f'{start}-{stop}/{file_size}'})

        with suppress(CancelledError):
            await response.prepare(request)
            await stream.seek(start)

            bytes_todo = stop - start
            bytes_done = 0
            self._logger.info('Got range request for %s-%s (%s bytes)', start, stop, bytes_todo)
            piecelen = download.get_def().get_piece_length()

            # If we don't have enough to return the next piece, we wait with sending data until we have 5MB
            if stream.get_byte_progress([(file_index, start, start + piecelen)]) < 1:
                while stream.get_byte_progress([(file_index, start, start + 5 * 1024 ** 2)]) < 1 \
                      and not request.transport.is_closing():
                    await sleep(1)

            while not request.transport.is_closing():
                data = await stream.read(piecelen)

                if len(data) == 0:
                    break
                if bytes_done + len(data) > bytes_todo:
                    endlen = bytes_todo - bytes_done
                    if endlen != 0:
                        await response.write(data[:endlen])
                        self._logger.info('Sent %s bytes', len(data))
                        bytes_done += endlen
                    break
                await response.write(data)
                bytes_done += len(data)
                self._logger.info('Sent %s bytes', len(data))

            return response
