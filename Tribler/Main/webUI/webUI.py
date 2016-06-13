import sys
import os
import logging
import random
from binascii import hexlify, unhexlify
import json
from functools import wraps
from traceback import print_exc
import cherrypy
from cherrypy import response
from cherrypy.lib.auth_basic import checkpassword_dict

from Tribler.Core.simpledefs import DOWNLOAD, UPLOAD
from Tribler.Core.DownloadConfig import DefaultDownloadStartupConfig


def jsonify(func):
    """JSON decorator for CherryPy"""
    @wraps(func)
    def wrapper(*args, **kw):
        try:
            value = func(*args, **kw)
            response.headers["Content-Type"] = "application/json"
            return json.dumps(value)
        except:
            print_exc()
            raise
    return wrapper


class WebUI(object):
    __single = None

    def __init__(self, library_manager, torrentsearch_manager, port):
        if WebUI.__single:
            raise RuntimeError("WebUI is singleton")
        WebUI.__single = self

        self._logger = logging.getLogger(self.__class__.__name__)

        self.currentTokens = set()
        self.currentTorrents = {}

        self.library_manager = library_manager
        self.torrentsearch_manager = torrentsearch_manager
        self.guiUtility = library_manager.guiUtility
        self.port = port

        self.started = False
        self.hasauth = False

    def getInstance(*args, **kw):
        if WebUI.__single is None:
            WebUI(*args, **kw)
        return WebUI.__single
    getInstance = staticmethod(getInstance)

    def delInstance(*args, **kw):
        WebUI.__single = None
    delInstance = staticmethod(delInstance)

    def start(self):
        if not self.started:
            self.started = True

            current_dir = os.path.join(self.guiUtility.utility.getPath(), 'Tribler', 'Main', 'webUI')
            config = {'/': {'tools.staticdir.root': current_dir,
                            'tools.staticdir.on': True,
                            'tools.staticdir.dir': "static",
                            'response.headers.connection': "close",
                            }
                      }

            if self.hasauth:
                userpassdict = {'hello': 'world'}
                checkpassword = checkpassword_dict(userpassdict)
                config['/'] = {'tools.auth_basic.on': True,
                               'tools.auth_basic.realm': 'Tribler-WebUI',
                               'tools.auth_basic.checkpassword': checkpassword}

            app = cherrypy.tree.mount(self, '/gui', config)
            app.log.access_log.setLevel(logging.NOTSET)
            app.log.error_log.setLevel(logging.NOTSET)

            self.server = cherrypy._cpserver.Server()
            self.server.socket_port = self.port
            self.server._socket_host = '0.0.0.0'
            self.server.thread_pool = 5
            self.server.subscribe()
            self.server.start()

    def stop(self):
        if self.started:
            self.server.stop()

    def clear_text(self, mypass):
        return mypass

    @cherrypy.expose
    @jsonify
    def index(self, **args):
        for key, value in args.iteritems():
            self._logger.debug("webUI: request %s %s", key, value)

        if len(args) == 0:
            raise cherrypy.HTTPRedirect("/gui/index.html")

        return_dict = {}
        if len(self.currentTokens) == 0:
            self.currentTokens.add(str(args['token']))

        if str(args['token']) in self.currentTokens:
            if 'action' in args:
                return_dict = self.doAction(args)

            if 'list' in args:
                return_dict = self.doList(args)

        return_dict['build'] = 1
        self._logger.debug("webUI: result %s", return_dict)
        return return_dict

    @cherrypy.expose(alias='token.html')
    def token(self, **args):
        new_token = ''.join(random.choice('0123456789ABCDEF') for i in range(60))
        self.currentTokens.add(new_token)
        self._logger.debug("webUI: new_token %s", new_token)
        return "<html><body><div id='token' style='display:none;'>%s</div></body></html>" % new_token

    def doList(self, args):
        _, torrents = self.library_manager.getHitsInCategory()

        return_dict = {'label': []}

        new_torrent_list = []
        for i, torrent in enumerate(torrents):
            torrent_list = [hexlify(torrent.infohash)]

            state = 0
            if 'checking' in torrent.state:
                state += 2
            else:
                state += 8

            if 'active' in torrent.state:
                state += 1 + 64 + 128

            torrent_list.append(state)

            torrent_list.append(torrent.name.encode('utf8'))
            torrent_list.append(torrent.length)

            ds = torrent.ds
            if ds:
                progress = ds.get_progress()

                stats = ds.get_seeding_statistics()
                if stats:
                    dl = stats['total_down']
                    ul = stats['total_up']
                else:
                    dl = ds.get_total_transferred(DOWNLOAD)
                    ul = ds.get_total_transferred(UPLOAD)

                seeds, peers = ds.get_num_seeds_peers()
                down_speed = ds.get_current_speed('down')
                up_speed = ds.get_current_speed('up')
                eta = ds.get_eta() or sys.maxsize
            else:
                progress = torrent.progress
                dl = 0
                ul = 0

                seeds = peers = 0
                down_speed = up_speed = 0
                eta = sys.maxsize

            torrent_list.append(int(progress * 1000))
            dl = max(0, progress * torrent.length)
            torrent_list.append(dl)
            torrent_list.append(ul)

            if dl == 0:
                if ul != 0:
                    ratio = sys.maxsize
                else:
                    ratio = 0
            else:
                ratio = 1.0 * ul / dl

            torrent_list.append(int(ratio * 1000))
            torrent_list.append(up_speed)
            torrent_list.append(down_speed)
            torrent_list.append(eta)
            torrent_list.append('')

            torrent_list.append(peers)
            torrent_list.append(peers)
            torrent_list.append(seeds)
            torrent_list.append(seeds)
            torrent_list.append(1)
            torrent_list.append(i + 1)
            torrent_list.append(torrent.length - dl)

            new_torrent_list.append(torrent_list)

        if 'cid' in args:
            cache_id = int(args['cid'])
            old_torrent_list = self.currentTorrents.get(cache_id, [])
            # step 1: create dict
            new_torrent_dict = {}
            for torrent in new_torrent_list:
                new_torrent_dict[torrent[0]] = torrent

            # step 2: create torrentp (changed torrents) and torrentm (removed torrents)
            return_dict['torrentp'] = []
            return_dict['torrentm'] = []
            for torrent in old_torrent_list:
                key = torrent[0]
                if key not in new_torrent_dict:
                    return_dict['torrentm'].append(key)
                else:
                    newtorrent = new_torrent_dict[key]
                    if newtorrent != torrent:
                        return_dict['torrentp'].append(newtorrent)
                    del new_torrent_dict[key]

            for torrent in new_torrent_dict.itervalues():
                return_dict['torrentp'].append(torrent)

        else:
            return_dict['torrents'] = new_torrent_list
            cache_id = 0

        cache_id += 1
        self.currentTorrents[cache_id] = new_torrent_list
        return_dict['torrentc'] = cache_id

        keys = self.currentTorrents.keys()[:-10]
        for key in keys:
            del self.currentTorrents[key]

        return return_dict

    def doAction(self, args):
        action = args['action']

        if action == 'add-url':
            url = args['s']
            destdir = DefaultDownloadStartupConfig.getInstance().get_dest_dir()

            if url.startswith("http"):
                self.guiUtility.frame.startDownloadFromUrl(url, destdir)
            elif url.startswith("magnet:"):
                self.guiUtility.frame.startDownloadFromMagnet(url, destdir)

        elif action == 'getprops':
            return self.doProps(args)

        elif action == 'getfiles':
            return self.doFiles(args)

        elif action == 'getsettings':
            return self.doSettings(args)

        elif 'hash' in args:
            if isinstance(args.get('hash', ''), basestring):
                infohashes = [args.get('hash', '')]
            else:
                infohashes = args['hash']

            for h in infohashes:
                infohash = unhexlify(h)

                torrent = self.library_manager.getTorrentFromInfohash(infohash)
                if action in ['start', 'forcestart', 'unpause']:
                    self.library_manager.resumeTorrent(torrent)
                elif action in ['stop', 'pause']:
                    self.library_manager.stopTorrent(torrent.infohash)
                elif action == 'remove':
                    self.library_manager.deleteTorrent(torrent)
                elif action == 'removedata':
                    self.library_manager.deleteTorrent(torrent, removecontent=True)

        return {}

    def doProps(self, args):
        infohash = unhexlify(args.get('hash', ''))
        torrent = self.library_manager.getTorrentFromInfohash(infohash)
        coltorrent = self.torrentsearch_manager.loadTorrent(torrent)
        return_dict = {'props': []}

        torrent_dict = {'hash': hexlify(torrent.infohash),
                        'trackers': "\r\n".join(coltorrent.trackers),
                        'ulrate': 0,
                        'dlrate': 0,
                        'superseed': 1,
                        'dht': 1,
                        'pex': 1,
                        'seed_override': 0}

        if torrent.ds:
            stats = torrent.ds.get_seeding_statistics()
            if stats:
                dl = stats['total_down']
                ul = stats['total_up']
            else:
                dl = torrent.ds.get_total_transferred(DOWNLOAD)
                ul = torrent.ds.get_total_transferred(UPLOAD)

            if dl == 0:
                if ul != 0:
                    ratio = sys.maxsize
                else:
                    ratio = 0
            else:
                ratio = 1.0 * ul / dl

            torrent_dict['seed_ratio'] = ratio
            torrent_dict['seed_time'] = stats['time_seeding']
        else:
            torrent_dict['seed_ratio'] = 0
            torrent_dict['seed_time'] = 0
        torrent_dict['ulslots'] = -1

        return_dict['props'].append(torrent_dict)
        return return_dict

    def doFiles(self, args):
        infohash = unhexlify(args.get('hash', ''))
        torrent = self.library_manager.getTorrentFromInfohash(infohash)
        coltorrent = self.torrentsearch_manager.loadTorrent(torrent)
        return_dict = {'files': []}

        return_dict['files'].append(hexlify(torrent.infohash))
        if torrent.ds:
            completion = torrent.ds.get_files_completion()
        else:
            completion = []

        files = []
        for filename, size in coltorrent.files:
            f = [filename, size, 0, 2]
            for cfile, cprogress in completion:
                if cfile == filename:
                    f[2] = cprogress * size
                    break

            files.append(f)
        return_dict['files'].append(files)
        return return_dict

    def doSettings(self, args):
        return {"settings": []}
