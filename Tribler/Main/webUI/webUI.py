import cherrypy
import random
import sys
import os
from binascii import hexlify,unhexlify
from Tribler.Core.simpledefs import DOWNLOAD, UPLOAD

import json
from functools import wraps
from cherrypy import response, expose


DEBUG = False


def jsonify(func):
    '''JSON decorator for CherryPy'''
    @wraps(func)
    def wrapper(*args, **kw):
        value = func(*args, **kw)
        response.headers["Content-Type"] = "application/json"
        return json.dumps(value)

    return wrapper


class WebUI():
    __single = None
    
    def __init__(self, library_manager, torrentsearch_manager, port):
        if WebUI.__single:
            raise RuntimeError, "WebUI is singleton"
        WebUI.__single = self
        
        self.currentTokens = set()
        self.currentTorrents = {}
        
        
        self.library_manager = library_manager
        self.torrentsearch_manager = torrentsearch_manager
        self.guiUtility = library_manager.guiUtility
        self.port = port
        
        self.started = False

    def getInstance(*args, **kw):
        if WebUI.__single is None:
            WebUI(*args, **kw)
        return WebUI.__single
    getInstance = staticmethod(getInstance)
    
    def start(self):
        if not self.started:
            self.started = True
            current_dir = os.path.dirname(os.path.abspath(__file__))
            
            current_dir = os.path.join(self.guiUtility.utility.getPath(), 'Tribler', 'Main', 'webUI')
            
            cherrypy.server.socket_host = "0.0.0.0"
            cherrypy.server.socket_port = self.port
            cherrypy.server.thread_pool = 5
            cherrypy.server.environment = "production"
            cherrypy.log.screen = False
            
            config = {'/': {
                            'tools.staticdir.root': current_dir, 
                            'tools.staticdir.on': True,
                            'tools.staticdir.dir': "static",
                          }
                      }
            cherrypy.tree.mount(self, '/gui', config)
            cherrypy.engine.start()
    
    def stop(self):
        if self.started:
            cherrypy.engine.stop()
    
    def clear_text(self, mypass):    
        return mypass
    
    @cherrypy.expose
    @jsonify
    def index(self, **args):
        if DEBUG:
            for key, value in args.iteritems():
                print >> sys.stderr, "webUI: request",key, value
        
        if len(args) == 0:
            raise cherrypy.HTTPRedirect("/gui/index.html")
        
        returnDict = {}
        if len(self.currentTokens) == 0:
            self.currentTokens.add(str(args['token']))
        
        if str(args['token']) in self.currentTokens:
            if 'list' in args:
                returnDict = self.doList(args)
            elif 'action' in args:
                returnDict = self.doAction(args)
                
        returnDict['build'] = 1
        if DEBUG:
            print >> sys.stderr, "webUI: result",returnDict
        return returnDict
            
    @cherrypy.expose(alias = 'token.html')
    def token(self, **args):
        newToken = ''.join(random.choice('0123456789ABCDEF') for i in range(60))
        self.currentTokens.add(newToken)
        if DEBUG:
            print >> sys.stderr, "webUI: newToken", newToken
        return "<html><body><div id='token' style='display:none;'>%s</div></body></html>"%newToken
    
    def doList(self, args):
        _,_,torrents = self.library_manager.getHitsInCategory()
        
        returnDict = {}
        returnDict['label'] = []
        
        newTorrentList = []
        for i, torrent in enumerate(torrents):
            torrentList = []
            torrentList.append(hexlify(torrent.infohash))
            
            if 'stopped' in torrent.state:
                torrentList.append(200)
            else:
                torrentList.append(201)
            
            torrentList.append(torrent.name.encode('utf8'))
            torrentList.append(torrent.length)
            
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
                downS = ds.get_current_speed('down')*1024 
                upS = ds.get_current_speed('up')*1024
                eta = ds.get_eta()
            else:
                progress = torrent.progress
                dl = 0
                ul = 0
                
                seeds = peers = 0
                downS = upS = 0
                eta = sys.maxint
            
            torrentList.append(int(progress*1000))
            dl = max(0, progress * torrent.length)
            torrentList.append(dl)
            torrentList.append(ul)
            
            if dl == 0L:
                if ul != 0L:
                    ratio = sys.maxint
                else:
                    ratio = 0
            else:
                ratio = 1.0*ul/dl
            
            torrentList.append(int(ratio*1000))
            torrentList.append(upS)
            torrentList.append(downS)
            torrentList.append(eta)
            torrentList.append('')
            
            torrentList.append(peers)
            torrentList.append(peers)
            torrentList.append(seeds)
            torrentList.append(seeds)
            torrentList.append(1)
            torrentList.append(i + 1)
            torrentList.append(torrent.length - dl)
            
            newTorrentList.append(torrentList)
        
        if 'cid' in args:
            cacheId = int(args['cid'])
            oldTorrentList = self.currentTorrents.get(cacheId,[])
            #step 1: create dict
            newTorrentDict = {}
            for torrent in newTorrentList:
                newTorrentDict[torrent[0]] = torrent
            
            #step 2: create torrentp (changed torrents) and torrentm (removed torrents)
            returnDict['torrentp'] = []
            returnDict['torrentm'] = []
            for torrent in oldTorrentList:
                key = torrent[0]
                if key not in newTorrentDict:
                    returnDict['torrentm'].append(key)
                else:
                    newtorrent = newTorrentDict[key]
                    if newtorrent != torrent:
                        returnDict['torrentp'].append(newtorrent)
                    del newTorrentDict[key]
            
            for torrent in newTorrentDict.itervalues():
                returnDict['torrentp'].append(torrent)
            
        else:
            returnDict['torrents'] = newTorrentList
            cacheId = 0
            
        cacheId += 1
        self.currentTorrents[cacheId] = newTorrentList
        returnDict['torrentc'] = cacheId
        
        keys = self.currentTorrents.keys()[:-10]
        for key in keys:
            del self.currentTorrents[key]
        
        return returnDict
    
    def doAction(self, args):
        action = args['action']
        
        if action == 'add-url':
            self.library_manager.startDownloadFromUrl(args['s'], useDefault = True)
            
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
            
            for hash in infohashes:
                infohash = unhexlify(hash)
        
                torrent = self.library_manager.getTorrentFromInfohash(infohash)
                if action in ['start', 'forcestart', 'unpause']:
                    self.library_manager.resumeTorrent(torrent)
                elif action in ['stop', 'pause']:
                    self.library_manager.stopTorrent(torrent)
                elif action == 'remove':
                    self.library_manager.deleteTorrent(torrent)
                elif action == 'removedata':
                    self.library_manager.deleteTorrent(torrent, removecontent = True)
                    
        return {}
    
    def doProps(self, args):
        infohash = unhexlify(args.get('hash', ''))
        torrent = self.library_manager.getTorrentFromInfohash(infohash)
        coltorrent = self.torrentsearch_manager.loadTorrent(torrent)
        returnDict = {'props': []}
        
        torrentDict = {}
        torrentDict['hash'] = hexlify(torrent.infohash)
        torrentDict['trackers'] = "\r\n".join(coltorrent.trackers)
        torrentDict['ulrate'] = 0
        torrentDict['dlrate'] = 0
        torrentDict['superseed'] = 1
        torrentDict['dht'] = 1
        torrentDict['pex'] = 1
        torrentDict['seed_override'] = 0
        
        if torrent.ds:
            stats = torrent.ds.get_seeding_statistics()
            if stats:
                dl = stats['total_down']
                ul = stats['total_up']
            else:
                dl = torrent.ds.get_total_transferred(DOWNLOAD)
                ul = torrent.ds.get_total_transferred(UPLOAD)
                
            if dl == 0L:
                if ul != 0L:
                    ratio = sys.maxint
                else:
                    ratio = 0
            else:
                ratio = 1.0*ul/dl
            
            torrentDict['seed_ratio'] = ratio
            torrentDict['seed_time'] = stats['time_seeding']
        else:
            torrentDict['seed_ratio'] = 0
            torrentDict['seed_time'] = 0 
        torrentDict['ulslots'] = -1
        
        returnDict['props'].append(torrentDict)
        return returnDict
    
    def doFiles(self, args):
        infohash = unhexlify(args.get('hash', ''))
        torrent = self.library_manager.getTorrentFromInfohash(infohash)
        coltorrent = self.torrentsearch_manager.loadTorrent(torrent)
        returnDict = {'files': []}
        
        returnDict['files'].append(hexlify(torrent.infohash))
        if torrent.ds:
            completion = torrent.ds.get_files_completion()
        else:
            completion = []
                
        files = []
        for filename, size  in coltorrent.files:
            file = [filename, size, 0, 2]
            for cfile, cprogress in completion:
                if cfile == filename:
                    file[2] = cprogress * size
                    break
            
            files.append(file)
        returnDict['files'].append(files)
        return returnDict
    
    def doSettings(self, args):
        return {"settings" : []}
        