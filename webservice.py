import wx
import sys

from threading import Thread
from string import upper

from traceback import print_exc
from cStringIO import StringIO

from Utility.helpers import getSocket
from Utility.constants import * #IGNORE:W0611


################################################################
#
# Class: WebDialog
#
# Let the user specify settings for the webservice
#
################################################################
class WebDialog(wx.Dialog):
    def __init__(self, parent):
        self.utility = parent.utility
        
        title = self.utility.lang.get('webinterfaceservice')

        pre = wx.PreDialog()
        pre.Create(parent, -1, title)
        self.this = pre.this
        self.parent = parent
        self.window = self.utility.window
        
        self.utility.webserver.webdlg = self
        
        WebRead = self.utility.webconfig.Read
        
        self.warnlowport = [False, WebRead('webport')]

#        # Change old config value
#        oldval = WebRead('webIP')
#        if (oldval == "Automatics") or (oldval == "Automatic"):
#            self.utility.webconfig.Write('webIP', "")
#            self.utility.webconfig.Flush()
#            ip_choice = ""
#        elif (oldval == "Loop Back"):
#            self.utility.webconfig.Write('webIP', "127.0.0.1")
#            self.utility.webconfig.Flush()
#            
#        newval = WebRead('webIP')
        newval = self.utility.webserver.getIP()
        if newval == "":
            default_ip = self.utility.lang.get('automatic')
        elif newval == "127.0.0.1":
            default_ip = self.utility.lang.get('loopback')
        else:
            default_ip = newval
        
        outerbox = wx.BoxSizer(wx.VERTICAL)
        
        outerbox.Add(wx.StaticText(self, -1, self.utility.lang.get('webinterfacetitle')), 0, wx.ALIGN_CENTER|wx.ALL, 10)

        ip_choices = [self.utility.lang.get('automatic'), self.utility.lang.get('loopback')]

        ipandport_box = wx.BoxSizer(wx.HORIZONTAL)
        ipandport_box.Add(wx.StaticText(self, -1, self.utility.lang.get('webip')), 0, wx.ALIGN_CENTER_VERTICAL|wx.ALL, 5)
        self.iptext = wx.ComboBox(self, -1, default_ip, wx.Point(-1, -1), wx.Size(100, -1), ip_choices, wx.CB_DROPDOWN|wx.CB_READONLY)
        ipandport_box.Add(self.iptext, 0, wx.ALIGN_CENTER_VERTICAL|wx.ALL, 5)
       
        ipandport_box.Add(wx.StaticText(self, -1, self.utility.lang.get('webport')), 0, wx.ALIGN_CENTER_VERTICAL|wx.ALL, 5)
        self.porttext = self.utility.makeNumCtrl(self, WebRead('webport'), max = 65536)
        ipandport_box.Add(self.porttext, 0, wx.ALIGN_CENTER_VERTICAL|wx.ALL, 5)

        outerbox.Add(ipandport_box, 0, wx.EXPAND|wx.ALL, 5)

        uniquekey_box = wx.BoxSizer(wx.HORIZONTAL)
        
        uniquekey_box.Add(wx.StaticText(self, -1, self.utility.lang.get('uniquekey')), 0, wx.ALIGN_CENTER_VERTICAL|wx.ALL, 5)
        self.keytext = wx.TextCtrl(self, -1, WebRead('webID'), wx.Point(-1, -1), wx.Size(165, -1))
        uniquekey_box.Add(self.keytext, 0, wx.ALIGN_CENTER_VERTICAL|wx.ALL, 5)
        
        outerbox.Add(uniquekey_box, 0, wx.EXPAND|wx.LEFT|wx.RIGHT, 5)

        self.permissions = [ ['webquery', 'allow_query'], 
                             ['webadd', 'allow_add'], 
                             ['webdelete', 'allow_delete'], 
                             ['webqueue', 'allow_queue'], 
                             ['webstop', 'allow_stop'], 
                             ['webresume', 'allow_resume'], 
                             ['webpause', 'allow_pause'], 
                             ['webclearallcompleted', 'allow_clearcompleted'], 
                             ['priority', 'allow_setprio'], 
                             ['webgetparam', 'allow_getparam'], 
                             ['websetparam', 'allow_setparam' ] ]

        self.perm_checkbox = wx.CheckListBox(self, -1, size = wx.Size(100, 120), style = wx.LB_SINGLE)
        perm_text = [self.utility.lang.get(item[0]) for item in self.permissions]
        self.perm_checkbox.Set(perm_text)
         
        for i in range(0, len(self.permissions)):
            param = self.permissions[i][1]
            checked = WebRead(param, "boolean")
            if checked:
                self.perm_checkbox.Check(i)
        
        outerbox.Add(wx.StaticText(self, -1, self.utility.lang.get('commandpermission')), 0, wx.ALL, 5)
        outerbox.Add(self.perm_checkbox, 0, wx.EXPAND|wx.LEFT|wx.RIGHT, 5)
  
        self.webautostart = wx.CheckBox(self, -1, self.utility.lang.get('webautostart'))
        
        outerbox.Add(self.webautostart, 0, wx.EXPAND|wx.ALL, 5)

        #CheckBox Set Value from Config
        #####################################
        self.webautostart.SetValue(WebRead('webautostart', "boolean"))

        self.actionbtn = wx.Button(self, -1, "")

        self.utility.webserver.updateLabels()

        applybtn  = wx.Button(self, wx.NewId(), self.utility.lang.get('apply'))
        self.Bind(wx.EVT_BUTTON, self.onApply, applybtn)

        okbtn  = wx.Button(self, wx.NewId(), self.utility.lang.get('ok'))
        self.Bind(wx.EVT_BUTTON, self.onOK, okbtn)

        cancelbtn = wx.Button(self, wx.ID_CANCEL, self.utility.lang.get('cancel'))
        self.Bind(wx.EVT_BUTTON, self.onClose, cancelbtn)
        
        self.Bind(wx.EVT_CLOSE, self.onClose)

        self.Bind(wx.EVT_BUTTON, self.OnAction, self.actionbtn)

        button_box = wx.BoxSizer(wx.HORIZONTAL)
        button_box.Add(applybtn, 0, wx.ALL, 5)
        button_box.Add(okbtn, 0, wx.ALL, 5)
        button_box.Add(cancelbtn, 0, wx.ALL, 5)

        outerbox.Add(self.actionbtn, 0, wx.ALIGN_CENTER|wx.ALL, 5)

        outerbox.Add(button_box, 0, wx.ALIGN_CENTER)

        self.SetAutoLayout(True)
        self.SetSizer(outerbox)
        self.Fit()

    def onOK(self, event = None):
        self.utility.webserver.webdlg = None
        if self.onApply():
            self.EndModal(wx.ID_OK)
            
    def onClose(self, event = None):
        self.utility.webserver.webdlg = None
        if event is not None:
            event.Skip()
        
    def onApply(self, event = None):
        self.saveParams()
        return True
        
    def saveParams(self):
        PORT = int(self.porttext.GetValue())

        if ((not self.warnlowport[0]
             or self.warnlowport[1] != str(PORT))
            and PORT < 1024):
            dlg = wx.MessageDialog(None, self.utility.lang.get('warningportunder1024') + "\n(" + str(PORT) + ")", self.utility.lang.get('warning'), wx.YES_NO|wx.ICON_INFORMATION)
            if dlg.ShowModal() == wx.ID_NO:
                dlg.Destroy()
                return False
            else:
                self.warnlowport[0] = True
            self.warnlowport[1] = str(PORT)
            dlg.Destroy()

        # Re-assign web parameters
        self.utility.webconfig.Write('webIP', self.iptext.GetStringSelection())
        self.utility.webconfig.Write('webport', str(self.porttext.GetValue()))
        self.utility.webconfig.Write('webID', self.keytext.GetValue())

        for i in range(0, self.perm_checkbox.GetCount()):
            param = self.permissions[i][1]
            checked = self.perm_checkbox.IsChecked(i)
            self.utility.webconfig.Write(param, checked, "boolean")
       
        if self.webautostart.GetValue():
            self.utility.webconfig.Write('webautostart', "1")
        else:
            self.utility.webconfig.Write('webautostart', "0")

        #######################################
        # Record New Config to webservice.conf
        #######################################
        self.utility.webconfig.Flush()
        
        return True
        
    def OnAction(self, event = None):
        if not self.utility.webserver.active:
            if self.saveParams():
                self.startWebService()
        else:
            self.stopWebService()

    def startWebService(self):
        ######################################
        # Start Web Interface Service
        ######################################
        self.utility.webserver.start()

    def stopWebService(self):
		# Stop Web Service
        self.utility.webserver.stop()
        
    def updateLabels(self):
        active = self.utility.webserver.active
        
        if active:
            label = self.utility.lang.get('stopservice')
        else:
            label = self.utility.lang.get('startservice')
        self.actionbtn.SetLabel(label)
        self.porttext.Enable(not active)
        self.keytext.Enable(not active)
        self.iptext.Enable(not active)


################################################################
#
# Class: WebListener
#
# Listens for webservice commands 
#
################################################################
class WebListener:
    def __init__(self, utility, webdlg = None):
        self.s = None
        self.utility = utility
        
        self.utility.webserver = self
        
        self.webdlg = webdlg
        
        self.active = False
        
        self.port = None
        self.ip = None
        
        self.client = WebClient(self.utility)

    def getIP(self):
        # Change old config value
        oldval = self.utility.webconfig.Read('webIP')
        if (oldval == "Automatics") or (oldval == "Automatic"):
            self.utility.webconfig.Write('webIP', "")
            self.utility.webconfig.Flush()
        elif (oldval == "Loop Back"):
            self.utility.webconfig.Write('webIP', "127.0.0.1")
            self.utility.webconfig.Flush()
#        if self.utility.webconfig.Read('webIP') == "Automatic":
#            IP = ""
#        else: #LoopBack
#            IP = "127.0.0.1"
#        return IP
        return self.utility.webconfig.Read('webIP')
    
    def getPort(self):
        try:
            PORT = self.utility.webconfig.Read('webport', "int")
        except:
            PORT = 56667
        return PORT
        
    def start(self):
        # Already running
        if self.active:
            return
        
        self.ip = self.getIP()   # Symbolic name meaning the local host
        self.port = self.getPort() # Arbitrary non-privileged port
        
        self.active = True
        self.updateLabels()
        
        webservice = Thread(target = self.startThread)
        webservice.setDaemon(False)
        webservice.start()
        
    def stop(self):
        # Not running, no need to stop
        if not self.active:
            return
        
        self.client.sendCmd("CLOSE|")
        
        self.port = None
        self.ip = None
        
        self.active = False
        self.updateLabels()
        
    def updateLabels(self):       
        self.utility.actions[ACTION_WEBSERVICE].updateButton()

        if self.webdlg is not None:
            self.webdlg.updateLabels()
        
    def startThread(self):
        self.s = getSocket(self.ip, self.port, "server")

        if self.s is None:
            #Display Dialog Can't open scoket
            dlg = wx.MessageDialog(None, self.utility.lang.get('cantopensocket') , self.utility.lang.get('socketerror'), wx.OK|wx.ICON_ERROR)
            dlg.ShowModal()
            dlg.Destroy()

            self.active = False
            self.updateLabels()
            return
        WebServiceCmd(self).go()


################################################################
#
# Class: WebClient
#
# Used to sent brief commands to the webservice
# (i.e.: use to send the shutdown command)
#
################################################################
class WebClient:
    def __init__(self, utility):
        self.utility = utility
        self.webserver = self.utility.webserver

    def sendCmd(self, command):
        # Web service isn't even active -- don't bother sending a message
        if not self.webserver.active:
            return False
                
        HOST = self.webserver.ip          # The remote host
        PORT = self.webserver.port        # The same port as used by the server
        s = getSocket(HOST, PORT)
        if s is None:
            dlg = wx.MessageDialog(None, self.utility.lang.get('cantconnectabcwebinterface') , self.utility.lang.get('socketerror'), wx.OK|wx.ICON_ERROR)
            dlg.ShowModal()
            dlg.Destroy()
            return False
            
        # if request is not close connection request
        # so it's torrent request copy .torrent
        # in backup torrent folder
        ##############################################
        mesg = "ID|" + self.utility.webconfig.Read('webID') + "\n" + command
        
        s.send(mesg)
        s.close()
        return True


################################################################
#
# Class: WebServiceCmd
#
# Processes the actual webservice commands
#
################################################################
class WebServiceCmd:
    def __init__(self, parent):
        self.parent = parent
        self.utility = self.parent.utility
        self.frame  = self.utility.frame
        
    def separate(self, info, splitchar = ","):
        try:
            separated = info.split(splitchar)
        except:
            self.conn.send("Feedback\nError=Bad Arguments")
            self.conn.close()
            separated = None
        return separated
        
    def getMappings(self, separated, splitchar = "="):
        mappings = {}
        
        for item in separated:
            try:
                pair = item.split(splitchar)
                mappings[pair[0]] = pair[1]
            except:
                self.conn.send("Feedback\nError=Bad Arguments")
                self.conn.close()
                mappings = None
                break
                
        return mappings

    def getTorrents(self, info = "", infohash_list = None):
        torrents = None
        
        if infohash_list is None:
            infohash_list = self.separate(info)
            if infohash_list is None:
                return torrents
        
        torrents = []
            
        for infohash in infohash_list:
            torrent = self.utility.queue.getABCTorrent(info_hash = infohash)
            
            if torrent is None:
                self.conn.send("Feedback\nError=No torrents match with this info hash: " + infohash + "\n")
                torrents = None
                break
            else:
                torrents.append(torrent)
                
        return torrents            

    def cmdSetParam(self, info):
        conn = self.conn
        
        if not self.utility.webconfig.Read('allow_setparam', "boolean"):
            conn.send("Feedback\nError=SETPARAM,Permission denied")
            return

        separated = self.separate(info, "|")
        if separated is None:
            return
            
        mappings = self.getMappings(separated)
        if mappings is None:
            return
            
        for param in mappings:
            self.utility.config.Write(param, mappings[param])
        self.utility.config.Flush()
        conn.send("Feedback\nOK")

    def cmdGetParam(self, info):
        conn = self.conn
        
        if not self.utility.webconfig.Read('allow_getparam', "boolean"):
            conn.send("Feedback\nError=GETPARAM,Permission denied")
            return

        separated = self.separate(info)
        if separated is None:
            return

        retmsg = ""
        Read = self.utility.config.Read
        for param in separated:
            value = Read(param)
            retmsg += value + "|"
        retmsg += "\n"
        conn.send("Feedback\n" + str(retmsg))
        
    def cmdClose(self):
        conn = self.conn
        
        self.utility.webserver.active = False
        self.utility.webserver.updateLabels()
        
        conn.close()
        self.parent.s.close()
        
#        sys.stderr.write("\nDone shutting down webservice")
               
    def cmdQuery(self, info = ""):
        conn = self.conn
        
        if not self.utility.webconfig.Read('allow_query', "boolean"):
            conn.send("Feedback\nError=QUERY,Permission denied")
            conn.close()
            return

        if info == "":
            self.QueryFields()
        else:
            fields = self.separate(info, ",")
            if fields is None:
                return

            self.QueryFields(fields)

    def QueryFields(self, fieldlist = None):
        conn = self.conn
        
        maxid = self.utility.list.columns.maxid

        # Default to returning all fields
        if fieldlist is None:
            fieldlist = range(4, maxid)
            
        oldfields    = { "filename"        : COL_TITLE, 
                         "progress"        : COL_PROGRESS, 
                         "btstatus"        : COL_BTSTATUS, 
                         "eta"             : COL_ETA, 
                         "dlspeed"         : COL_DLSPEED, 
                         "ulspeed"         : COL_ULSPEED, 
                         "ratio"           : COL_RATIO, 
                         "peers"           : COL_PEERS, 
                         "seeds"           : COL_SEEDS, 
                         "copies"          : COL_COPIES, 
                         "dlsize"          : COL_DLSIZE, 
                         "ulsize"          : COL_ULSIZE, 
                         "peeravgprogress" : COL_PEERPROGRESS, 
                         "totalspeed"      : COL_TOTALSPEED, 
                         "totalsize"       : COL_SIZE, 
                         "priority"        : COL_PRIO }
        
        fieldids = []
        
        retmsg = ""
        for req_field in fieldlist:
            try:
                # A field number was specified
                fieldid = int(req_field)
                if fieldid >= 4 and fieldid < maxid:
                    fieldids.append(fieldid)
                else:
                    conn.send("Feedback\nError=Invalid field ID (must be between 4 and " + str(maxid) + ") = " + req_field)
                    conn.close()
                    return                    
            except:
                # Old format -- a field name was specified
                if req_field in oldfields:
                    fieldid = oldfields[req_field]
                    fieldids.append(fieldid)
                else:
                    # Can't identify the field
                    conn.send("Feedback\nError=Unknown field name = " + req_field)
                    conn.close()
                    return

            retmsg += self.utility.lang.get("column" + str(fieldid) + "_text") + "|"

        retmsg += "Info Hash\n"

        for ABCTorrentTemp in self.utility.torrents["all"]:
            retmsg += ABCTorrentTemp.getInfo(fieldlist = fieldids)
        
        conn.send(retmsg)
        conn.close()
                
    def cmdAdd(self, info):
        conn = self.conn
        
        if not self.utility.webconfig.Read('allow_add', "boolean"):
            conn.send("Feedback\nError=ADD,Permission denied")
            return

        # What do we do if we don't have a default download location specified
        # and we call this from the webservice?
        ####################################################
        retmsg = self.utility.queue.addtorrents.AddTorrentURL(info, "web")
        conn.send("Feedback\n"+retmsg)
            
    def cmdDelete(self, info):
        conn = self.conn
        
        if upper(info) == "COMPLETED":
            if not self.utility.webconfig.Read('allow_clearcompleted', "boolean"):
                conn.send("Feedback\nError=CLEARCOMPLETED,Permission denied")
                return
                
            self.utility.actions[ACTION_CLEARCOMPLETED].action()
            conn.send("Feedback\nOK")
        else:
            if not self.utility.webconfig.Read('allow_delete', "boolean") != "1":
                conn.send("Feedback\nError=DELETE,Permission denied")
                return
            
            torrents = self.getTorrents(info)
            if torrents is None:
                return

            self.utility.actionhandler.procREMOVE(torrents)
            conn.send("Feedback\nOK")
                
    def cmdResume(self, info = "ALL"):
        conn = self.conn

        if not self.utility.webconfig.Read('allow_resume', "boolean"):
            conn.send("Feedback\nError=RESUME,Permission denied")
            return
        
        if upper(info) == "ALL":
            self.utility.actions[ACTION_UNSTOPALL].action()
            conn.send("Feedback\nOK")   
        else:
            torrents = self.getTorrents(info)
            if torrents is None:
                return

            self.utility.actionhandler.procRESUME(torrents)
            conn.send("Feedback\nOK")
                               
    def cmdStop(self, info = "ALL"):
        conn = self.conn
        
        if not self.utility.webconfig.Read('allow_stop', "boolean"):
            conn.send("Feedback\nError=STOP,Permission denied")
            return
        
        if upper(info) == "ALL":
            self.utility.actions[ACTION_STOPALL].action()
            conn.send("Feedback\nOK")
        else:
            torrents = self.getTorrents(info)
            if torrents is None:
                return

            self.utility.actionhandler.procSTOP(torrents)
            conn.send("Feedback\nOK")

    def cmdPause(self, info, release = False):
        conn = self.conn
        
        if not self.utility.webconfig.Read('allow_pause', "boolean"):
            conn.send("Feedback\nError=PAUSE,Permission denied")
            conn.close()
            return
            
        if upper(info) == "ALL":
            torrents = self.utility.torrents["active"].keys()
        else:
            torrents = self.getTorrents(info)
            if torrents is None:
                return
                       
        self.utility.actionhandler.procPAUSE(torrents, release = release)
        conn.send("Feedback\nOK")
                        
    def cmdQueue(self, info = "ALL"):
        conn = self.conn
        
        if not self.utility.webconfig.Read('allow_queue', "boolean"):
            conn.send("Feedback\nError=QUEUE,Permission denied")
            return

        if upper(info) == "ALL":
            torrents = self.utility.torrents["all"]
        else:
            torrents = self.getTorrents(info)
            if torrents is None:
                return

        self.utility.actionhandler.procQUEUE(torrents)
        conn.send("Feedback\nOK")
        
    def cmdPriority(self, info):
        conn = self.conn
        
        if not self.utility.webconfig.Read('allow_setprio', "boolean"):
            conn.send("Feedback\nError=PRIORITY,Permission denied")
            return
            
        separated = self.separate(info, "|")
        if separated is None:
            return
            
        mappings = self.getMappings(separated, ",")
        if mappings is None:
            return
        
        for infohash in mappings:
            value = mappings[infohash]
            error = False
            try:
                prio = int(value)
                if (prio < 0) or (prio > 4):
                    error = True
            except:
                error = True
            if error:
                conn.send("Feedback\nError=Priority must be a number from 0-4")
                conn.close()
                return

        hashlist = [infohash for infohash in mappings]
        torrents = self.getTorrents(infohash_list = hashlist)
        if torrents is None:
            return
            
        for torrent in torrents:
            torrent.changePriority(prio)
            
        conn.send("Feedback\nOK")
        
    def go(self):
        while 1:
            conn, addr = self.parent.s.accept()
            self.conn = conn
            try:
                try:
                    data = conn.recv(5048)
                except:
                    try:
                        conn.close()
                    except:
                        pass
                    continue
                
                try:
                    idline, cmdline = data.split("\n")
                except:
                    conn.send("Feedback\nError=You need unique ID to command ABC!")
                    conn.close()
                    continue
    
                try:
                    idtag   = idline.split("|")
                    idkey   = idtag[0]
                    idvalue = idtag[1]
                except:
                    conn.send("Feedback\nError=You need unique ID to command ABC!")
                    conn.close()
                    continue

                if idkey != "ID":
                    conn.send("Feedback\nError=You need unique ID to command ABC!")
                    conn.close()
                    continue
                else:
                    if idvalue != self.utility.webconfig.Read('webID'):
                        conn.send("Feedback\nError=Incorrect unique ID")
                        conn.close()
                        continue
                
                try:                
                    cmd, info = cmdline.split("|")
                except:
                    #Bad Command
                    conn.send("Feedback\nError=Command should end with |")
                    conn.close()
                    continue
                
                sys.stdout.write('Web Request Recieved.\n' + data + '\n')
                
                # Convert the command to upper case
                cmd = upper(cmd)
                
                if cmd == "CLOSE" or self.utility.abcquitting:
                    self.cmdClose()
                    return
                
#                elif cmd == "KEEPALIVE":
#                    # Don't actually do anything
#                    pass
                
                elif cmd == "QUERY":
                    self.cmdQuery(info)
                                       
                elif cmd == "ADD":
                    self.cmdAdd(info)
                        
                elif cmd == "DELETE":
                    self.cmdDelete(info)
            
                elif cmd == "RESUME":
                    self.cmdResume(info)
    
                elif cmd == "PAUSE":
                    self.cmdPause(info)

                elif cmd == "UNPAUSE":
                    self.cmdPause(info, release = True)
    
                elif cmd == "STOP":
                    self.cmdStop(info)
    
                elif cmd == "QUEUE":
                    self.cmdQueue(info)
                    
                elif cmd == "PRIORITY":
                    self.cmdPriority(info)

                elif cmd == "SETPARAM":
                    self.cmdSetParam(info)
                    
                elif cmd == "GETPARAM":
                    self.cmdGetParam(info)
                    
                elif cmd == "GETSTRING":
                    conn.send("String\n" + self.utility.lang.get(info))

                elif cmd == "VERSION":
                    conn.send("Version\n" + self.utility.lang.get('version'))

                else: # Bad Command
                    conn.send("Feedback\nError=Command not found: " + cmd)
                    pass
            except:
                pass
            conn.close()
                
