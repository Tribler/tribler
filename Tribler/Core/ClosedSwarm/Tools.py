# Written by Njaal Borch
# see LICENSE.txt for license information
#
# Arno TODO: move this to ../Tools/, wx not allowed in ../Core
#

import re
import urllib
import urllib2

def wx_get_poa(root_window=None):
    """
    Pop up a graphical file selector
    """
    import wx
    import sys
    print >>sys.stderr, "Using GUI poa browser"
    fd = wx.FileDialog(root_window, "Select Proof of Access", wildcard="*.poa", style=wx.OPEN)
    if fd.ShowModal() == wx.ID_OK:
        return read_poa_from_file(fd.GetPath())
    raise Exception("User aborted")
    

def wx_get_http_poa(url, swarm_id, perm_id, root_window=None):
    """
    Pop up a graphical authorization thingy if required by the
    web server 
    """

    def auth_handler(realm):
        """
        As for username,password
        """
        import wx
        import sys
        print >>sys.stderr, "Using GUI poa browser"
        
        pw = wx.Dialog(root_window, -1, "Authenticate")

        vert = wx.BoxSizer(wx.VERTICAL)
        label_1 = wx.StaticText(pw, -1, "Authentication for %s reqired"%realm)
        vert.Add(label_1, 0, wx.EXPAND | wx.LEFT, 10)
    
        horiz = wx.BoxSizer(wx.HORIZONTAL)
        vert.Add(horiz, 0, 0, 0)
        label_2 = wx.StaticText(pw, -1, "Username")
        label_2.SetMinSize((70,15))
        horiz.Add(label_2, 0, wx.LEFT, 0)
        pw.username = wx.TextCtrl(pw, -1, "")
        horiz.Add(pw.username, 0, wx.LEFT, 0)

        horiz = wx.BoxSizer(wx.HORIZONTAL)
        vert.Add(horiz, 0, 0, 0)
        pw.pwd = wx.TextCtrl(pw, -1, "", style=wx.TE_PASSWORD)
        label_3  = wx.StaticText(pw, -1, "Password")
        label_3.SetMinSize((70,15))
        horiz.Add(label_3, 0, wx.LEFT, 0)
        horiz.Add(pw.pwd, 0, wx.LEFT, 0)

        horiz = wx.BoxSizer(wx.HORIZONTAL)
        vert.Add(horiz, 0, wx.LEFT, 0)

        horiz.Add(wx.Button(pw, wx.ID_CANCEL), 0,0,0)
        ok = wx.Button(pw, wx.ID_OK)
        ok.SetDefault()
        horiz.Add(ok, 0,0,0)

        pw.username.SetFocus()
        order = (pw.username, pw.pwd, ok)
        for i in xrange(len(order) - 1):
            order[i+1].MoveAfterInTabOrder(order[i])

        pw.SetSizer(vert)
        vert.Fit(pw)
        pw.Layout()

        try:
            if pw.ShowModal() == wx.ID_OK:
                return (pw.username.GetValue(), pw.pwd.GetValue())
        finally:
            pw.Destroy()

        raise Exception("User aborted")

    w = web_get_poa(url, swarm_id, perm_id, auth_handler)    
    return w.get_poa()
    

class web_get_poa:
    """
    Class that will call the auth_handler if authentication
    is required
    """
    
    def __init__(self, url, swarm_id, perm_id, auth_handler=None):

        self.url = url
        self.swarm_id = swarm_id
        self.perm_id = perm_id
        self.auth_handler = auth_handler

        
    def get_poa(self, credentials=None):
        """
        Try to fetch a POA
        """

        if credentials and len(credentials) == 4:
            (protocol, realm, name, password) = credentials
            password_mgr = urllib2.HTTPPasswordMgrWithDefaultRealm()
            password_mgr.add_password(realm, self.url, name, password)
            if protocol.lower() == "digest":
                handler = urllib2.HTTPDigestAuthHandler(password_mgr)
            elif protocol.lower() == "basic":
                handler = urllib2.HTTPBasicAuthHandler(password_mgr)
            else:
                raise Exception("Unknown authorization protocol: '%s'"%protocol)
                
            opener = urllib2.build_opener(handler)
            urllib2.install_opener(opener)

        values = {'swarm_id':self.swarm_id,
                  'perm_id':self.perm_id}

        try:
            data = urllib.urlencode(values)
            req = urllib2.Request(self.url, data)
            response = urllib2.urlopen(req)
        except urllib2.HTTPError,e:
            # Need authorization?
            if e.code == 401 and not credentials:
                try:
                    type, realm = e.headers["WWW-Authenticate"].split()
                    m = re.match('realm="(.*)"', realm)
                    if m:
                        realm = m.groups()[0]
                    else:
                        raise Exception("Bad www-authenticate reponse")
                except Exception,e:
                    raise Exception("Authentication failed: %s"%e)
                        
                if self.auth_handler:
                    name, passwd = self.auth_handler(realm)
                    if name and passwd:
                        credentials = (type, realm, name, passwd)
                        return self.get_poa(credentials)
                    
            raise Exception("Could not get POA: %s"%e)
        except urllib2.URLError,e:
            raise Exception("Could not get POA: %s"%e.reason)
        

        # Connected ok, now get the POA
        try:
            poa_str = response.read()
            from Tribler.Core.ClosedSwarm import ClosedSwarm
            return ClosedSwarm.POA.deserialize(poa_str)
        except Exception,e:
            raise Exception("Could not fetch POA: %s"%e)
    
        raise Exception("Could not get POA: Unknown reason")


    
