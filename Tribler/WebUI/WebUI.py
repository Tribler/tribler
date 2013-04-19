# Written by Riccardo Petrocco
# see LICENSE.txt for license information

# TODO
# 1- romove only torrent, not the content
# 2- confirm dialog on removing!

import sys, os
import time
import random
import urllib
import urlparse
import cgi
import binascii
import copy
from cStringIO import StringIO
from traceback import print_exc,print_stack
from threading import RLock,Condition
from base64 import encodestring

# json is Python 2.6, P2P-Next std is 2.5.
try:
    import simplejson as json
except ImportError:
    import json


from Tribler.Core.API import *
from Tribler.Video.VideoServer import AbstractPathMapper

try:
    import wxversion
    wxversion.select('2.8')
except:
    pass
import wx

from Tribler.Plugin.defs import *
from Tribler.__init__ import LIBRARYNAME

DEBUG = False
PATH = 'webUI'


def streaminfo404():
    return {'statuscode':404, 'statusmsg':'404 Not Found'}


class WebIFPathMapper(AbstractPathMapper):

    binaryExtensions = ['.gif', '.png', '.jpg', '.js', '.css']
    contentTypes = {
        '.css': 'text/css',
        '.gif': 'image/gif',
        '.jpg': 'image/jpg',
        '.png': 'image/png',
        '.js' : 'text/javascript',
        '.html': 'text/html',
    }

    def __init__(self,bgApp, session):
        self.bgApp = bgApp
        self.session = session
        # Dict of dict in the for of:
        # {
        #   infohash_download1 :
        #       {
        #        id : infohash
        #        name: ..
        #        status: ..
        #        ...
        #       }
        #   infohash_download2 :
        #   ...
        # }
        self.downspeed = 0
        self.upspeed = 0
        self.lastreqtime = time.time()

        ext = sys.argv[0].lower()

        if ext.endswith('.exe'):
            self.webUIPath = os.path.abspath(os.path.dirname(sys.argv[0]))
        else:
            self.webUIPath = os.getcwd()

        # Arno,2010-07-16: Speeds are just calculated from periodically
        # retrieved values, instead of pseudo-synchronously.
        #
        self.session.set_download_states_callback(self.speed_callback)


    def get(self,urlpath):
        try:
            return self.doget(urlpath)
        except:
            print_exc()


    def doget(self,urlpath):

        """
        Possible paths:
        /search<application/x-www-form-urlencoded query>
        """
        if not urlpath.startswith(URLPATH_WEBIF_PREFIX):
            return streaminfo404()

        self.lastreqtime = time.time()

        fakeurl = 'http://127.0.0.1'+urlpath
        o = urlparse.urlparse(fakeurl)

        if DEBUG:
            print >>sys.stderr,"webUI: path", urlpath

        path = urlpath[7:]


        if len(path) == 0:
            # Get the default status page!
            #if urlpath == '' or urlpath == 'index.html'
            page = self.statusPage()
            pageStream = StringIO(page)

#            print >>sys.stderr, "-------------page-----------------", fakeurl, "\n" , o
#            print >>sys.stderr, "-------------page-----------------", page, "\n"
#            print >>sys.stderr, "-------------page-----------------", pageStream, "\n"
            #try:
            return {'statuscode':200,'mimetype': 'text/html', 'stream': pageStream, 'length': len(page)}

        elif len(path) > 0:
            if path == "permid.js":
                try:
                    permid = encodestring(self.bgApp.s.get_permid()).replace("\n", "")
                    txt = "var permid = '%s';"%permid
                    dataStream = StringIO(txt)
                except Exception,e:
                    print >> sys.stderr, "permid.js failure:", e
                    return {'statuscode': 500, 'statusmsg':'Bad permid'}

                return {'statuscode':200, 'mimetype':'text/javascript', 'stream':dataStream, 'length': len(txt)}

            # retrieve and send the right resource
            extension = os.path.splitext(path)[1]

            if extension in self.binaryExtensions:
                mode = 'rb'
            else:
                mode = 'r'

            # TODO
            try:
                absPath =  os.path.join(self.webUIPath, LIBRARYNAME, "WebUI", path)
            except:
                pass


            # retrieve resourse such as pages or images
            if urlpath[6] == '/' and os.path.isfile(absPath):


                fp = open(absPath, mode)
                data = fp.read()
                fp.close()
                dataStream = StringIO(data)


#                print >>sys.stderr, "-------------page-----------------", self.getContentType(extension), "\n"
#                print >>sys.stderr, "-------------page-----------------", dataStream, "\n"


                # Send response
                return {'statuscode':200,'mimetype': self.getContentType(extension), 'stream': dataStream, 'length': len(data)}

            elif urlpath[6] == '?':

                if DEBUG:
                    print >>sys.stderr,"webUI: received a GET request"

                # It's a GET request (webUI/?..), check for json format


                # Important!! For hashes we don't unquote the request, we just
                # replace the encoded quotes. Json will not parse the hashes
                # if decoded!! This is caused by the fact that Json does not accept
                # special chars like '/'.

                try:
                    req = urllib.unquote(urlpath[6:])
                    o = req.split('&')[1]
                    jreq = json.loads(o)
                except:
                    req = urlpath[6:].replace('%22', '"')
                    o = req.split('&')[1]
                    jreq = json.loads(o)

                try:
                    method = jreq['method']
                except:
                    return {'statuscode':504, 'statusmsg':'Json request in wrong format! At least a method has to be specified!'}

                try:
                    args = jreq['arguments']
                    if DEBUG:
                        print >> sys.stderr, "webUI: Got JSON request: " , jreq, "; method: ", method, "; arguments: ", args
                except:
                    args = None
                    if DEBUG:
                        print >> sys.stderr, "webUI: Got JSON request: " , jreq, "; method: ", method


                if args is None:
                # TODO check params
                    data = self.process_json_request(method)
                    if DEBUG:
                        print >>sys.stderr, "WebUI: response to JSON ", method, " request: ", data
                else:
                    data = self.process_json_request(method, args)
                    if DEBUG:
                        print >>sys.stderr, "WebUI: response to JSON ", method, " request: ", data, " arguments: ", args

                if data == "Args missing":
                    return {'statuscode':504, 'statusmsg':'Json request in wrong format! Arguments have to be specified!'}

                dataStream = StringIO(data)
                return {'statuscode':200,'mimetype': 'application/json', 'stream': dataStream, 'length': len(data)}

            else:
                # resource not found or in wrong format
                return streaminfo404()


    def process_json_request(self, method, args=None):
        try:
            return self.doprocess_json_request(method, args=args)
        except:
            print_exc()
            return json.JSONEncoder().encode({"success" : "false"})

    def doprocess_json_request(self, method, args=None):

        # Decode the infohash if present
        if args is not None:
            infohash = urllib.unquote( str(args['id']) )


        if DEBUG:
            print >>sys.stderr, "WebUI: received JSON request for method: ", method

        if method == "get_all_downloads":

            condition = Condition()
            dlist = []
            states_func = lambda dslist:self.states_callback(dslist,condition,dlist)
            self.session.set_download_states_callback(states_func)

            # asyncronous callbacks... wait for all the stats to be retrieved,
            # Arno: in this case it is important that the value is accurate to
            # prevent just deleted items to reappear.
            condition.acquire()
            condition.wait(5.0)
            condition.release()

            return json.JSONEncoder().encode({"downloads" : dlist})


        elif method == "pause_all":

            try:
                #downloads = self.session.get_downloads()
                wx.CallAfter(self.bgApp.gui_webui_stop_all_downloads, self.session.get_downloads())
                #for dl in downloads:
                #    dl.stop()

                return json.JSONEncoder().encode({"success" : "true"})


            except:
                return json.JSONEncoder().encode({"success" : "false"})


        elif method == "resume_all":

            try:
                #downloads = self.session.get_downloads()
                wx.CallAfter(self.bgApp.gui_webui_restart_all_downloads, self.session.get_downloads())

                #for dl in downloads:
                #    dl.restart()

                return json.JSONEncoder().encode({"success" : "true"})


            except:
                return json.JSONEncoder().encode({"success" : "false"})


        elif method == "remove_all":

            try:
                #downloads = self.session.get_downloads()
                wx.CallAfter(self.bgApp.gui_webui_remove_all_downloads, self.session.get_downloads())
                #for dl in downloads:
                #    self.session.remove_download(dl, True)

                return json.JSONEncoder().encode({"success" : "true"})

            except:
                return json.JSONEncoder().encode({"success" : "false"})


        elif method == "get_speed_info":

            # Arno, 2010-07-16: Return latest values periodically retrieved.
            return json.JSONEncoder().encode({"success" : "true", "downspeed": self.downspeed, "upspeed" : self.upspeed})

        # Methods that need arguments!!
        elif args is None:
            return "Args missing"


        elif method == "pause_dl":

            try:
                downloads = self.session.get_downloads()
                for dl in downloads:
                    if dl.get_def().get_infohash() == infohash:
                        wx.CallAfter(self.bgApp.gui_webui_stop_download, dl)

                return json.JSONEncoder().encode({"success" : "true"})

            except:
                return json.JSONEncoder().encode({"success" : "false"})


        elif method == "resume_dl":

            try:
                downloads = self.session.get_downloads()
                for dl in downloads:
                    if dl.get_def().get_infohash() == infohash:
                        wx.CallAfter(self.bgApp.gui_webui_restart_download, dl)

                return json.JSONEncoder().encode({"success" : "true"})

            except:
                return json.JSONEncoder().encode({"success" : "false"})


        elif method == "remove_dl":

            try:
                downloads = self.session.get_downloads()

                for dl in downloads:
                    if dl.get_def().get_infohash() == infohash:
                        wx.CallAfter(self.bgApp.gui_webui_remove_download, dl)

                return json.JSONEncoder().encode({"success" : "true"})
            except:
                return json.JSONEncoder().encode({"success" : "false"})


    def states_callback(self,dslist,condition,dlist):
        """ Called by Session thread """

        # Display some stats
        for ds in dslist:
            d = ds.get_download()

            infohash = urllib.quote(d.get_def().get_infohash())
#            infohash = (d.get_def().get_infohash()).toJSON()

            dl = {'id' : infohash, 'name': d.get_def().get_name(), 'status': dlstatus_strings[ds.get_status()], 'progress': ds.get_progress(), 'upload': ds.get_current_speed(UPLOAD), 'download': ds.get_current_speed(DOWNLOAD)}

            dlist.append(dl)

        condition.acquire()
        condition.notify()
        condition.release()
        return (0.0, False)


    def speed_callback(self,dslist):
        """ Called by Session thread """

        upspeed = 0
        downspeed = 0

        # Display some stats
        for ds in dslist:
            d = ds.get_download()

            upspeed += ds.get_current_speed(UPLOAD)
            downspeed += ds.get_current_speed(DOWNLOAD)

        self.downspeed = downspeed
        self.upspeed = upspeed

        # Arno,2010-07-16: Continuous
        return (1.0, [])


    def statusPage(self):

        page = '<!DOCTYPE html>'
        page += '<html>\n'

        # get the headers
        header =  os.path.join(self.webUIPath, LIBRARYNAME, "WebUI", "index", "head.html")
        if os.path.isfile(header):
            f = open(header)

            head = f.read()
            f.close
            page += head


        # get body
        body =  os.path.join(self.webUIPath, LIBRARYNAME, "WebUI", "index", "body.html")
        if os.path.isfile(body):
            f = open(body)
            tmp = f.read()
            f.close
            page += tmp

        page += '</html>'

        return page


    def getContentType(self, ext):
        """ Function to figure out content types """
        content_type = 'text/plain'

        if ext in self.contentTypes:
            content_type = self.contentTypes[ext]
        return content_type
