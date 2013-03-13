import sys
import wx
import wx.html as html

from webbrowser import open_new
from threading import Thread
from traceback import print_exc
from Tribler.Core.Utilities.timeouturlopen import urlOpenTimeout

################################################################
#
# Class: MyHtmlWindow
#
# Helper class to display html in a panel and handle clicking
# on urls.
#
################################################################
class MyHtmlWindow(html.HtmlWindow):
    def __init__(self, parent, id):
        html.HtmlWindow.__init__(self, parent, id, size=(400, 300))
        self.Bind(wx.EVT_SCROLLWIN, self.OnScroll)

    def OnScroll(self, event):
        event.Skip()

    def OnLinkClicked(self, linkinfo):
        t = Thread(target = open_new(linkinfo.GetHref()))
        t.setName( "AboutMeLinkOpen"+t.getName() )
        t.setDaemon(True)
        t.start()


################################################################
#
# Class: MyHtmlDialog
#
# Displays html formatted information in a dialog
#
################################################################
class MyHtmlDialog(wx.Dialog):
    def __init__(self, parent, title, content):
        wx.Dialog.__init__(self, parent, -1, title)

        btn = wx.Button(self, wx.ID_OK, " OK ")
        btn.SetDefault()

        color = self.GetBackgroundColour()
        bgcolor = "#%02x%02x%02x" % (color.Red(), color.Green(), color.Blue())

        about_html = "<HTML><HEAD><TITLE>" + title + "</TITLE></HEAD>" + \
                     "<BODY BGCOLOR=" + bgcolor + " TEXT=#000000>" + \
                     content + \
                     "</BODY></HTML>"

        self.html = MyHtmlWindow(self, -1)
        self.html.SetPage(about_html)

        buttonbox = wx.BoxSizer(wx.HORIZONTAL)
        buttonbox.Add(btn, 0, wx.ALL, 5)

        outerbox = wx.BoxSizer(wx.VERTICAL)
        outerbox.Add(self.html, 0, wx.EXPAND|wx.ALL, 5)
        outerbox.Add(buttonbox, 0, wx.ALIGN_CENTER)

        self.SetAutoLayout(True)
        self.SetSizer(outerbox)
        self.Fit()


################################################################
#
# Class: VersionDialog
#
# Show information about the current version of ABC
#
################################################################
class VersionDialog(MyHtmlDialog):
    def __init__(self, parent):
        self.parent = parent
        self.utility = parent.utility

        content = ""
        try :
            nu = self.hasNewVersion()
            if nu == 0:
                content += "<FONT SIZE=+1>"
                content += self.utility.lang.get('nonewversion')
                content += "<BR>\n"
                content += "</FONT>"
            elif nu == 1:
                content += "<FONT SIZE=+1>"
                newversion = self.utility.lang.get('hasnewversion')
                content += "<a href=" + self.update_url + ">" + newversion + "</a>"
                content += "<BR>\n"
                content += "</FONT>"
            else:
                content += "<FONT SIZE=+1>"
                content = self.utility.lang.get('cantconnectwebserver')
                content += "<BR>\n"
                content += "</FONT>"
        except:
            content = self.utility.lang.get('cantconnectwebserver')
            print_exc()

        title = self.utility.lang.get('abclatestversion')

        MyHtmlDialog.__init__(self, parent, title, content)


    def hasNewVersion(self):
        my_version = self.utility.getVersion()
        try:
            # Arno: TODO: don't let this be done by MainThread
            curr_status = urlOpenTimeout('http://tribler.org/version/',timeout=1).readlines()
            line1 = curr_status[0]
            if len(curr_status) > 1:
                self.update_url = curr_status[1].strip()
            else:
                self.update_url = 'http://tribler.org/'
            _curr_status = line1.split()
            self.curr_version = _curr_status[0]
            if self.newversion(self.curr_version, my_version):
                return 1
            else:
                return 0
        except:
            print_exc()
            return -1

    def newversion(self, curr_version, my_version):
        curr = curr_version.split('.')
        my = my_version.split('.')
        if len(my) >= len(curr):
            nversion = len(my)
        else:
            nversion = len(curr)
        for i in range(nversion):
            if i < len(my):
                my_v = int(my[i])
            else:
                my_v = 0
            if i < len(curr):
                curr_v = int(curr[i])
            else:
                curr_v = 0
            if curr_v > my_v:
                return True
            elif curr_v < my_v:
                return False
        return False

################################################################
#
# Class: AboutMeDialog
#
# Display credits information about who has contributed to ABC
# along with what software modules it uses.
#
################################################################
class AboutMeDialog(MyHtmlDialog):
    def __init__(self, parent):

        self.parent = parent
        self.utility = parent.utility

        bittornado_version = "0.3.13"
        py2exe_version = "0.6.2"
        nsis_version = "2.09"

        title = self.utility.lang.get('aboutabc')

#        # Start UI in Dialog
#        #######################
#
#        btn = wx.Button(self, wx.ID_OK, " OK ")
#        btn.SetDefault()
#
#        color = self.GetBackgroundColour()
#        bgcolor = "#%02x%02x%02x" % (color.Red(), color.Green(), color.Blue())

        wx_version = ""
        for v in wx.VERSION:
            s = str(v)+"."
            wx_version += s
        wx_version = wx_version.strip(".")

        major, minor, micro, releaselevel, serial = sys.version_info
        python_version = str(major) + "." + str(minor) + "." + str(micro)


        content =    "<B><CENTER>" + \
                       self.utility.lang.get('title') + " V" + self.utility.lang.get('version') + \
                     "</CENTER></B>" + \
                     "<FONT SIZE=-1>" + \
                     "<CENTER><BR>" + self.utility.lang.get('build_date') + "</CENTER>" + \
                     "<P>Tribler is an Internet TV application." + \
                     "<BR>It allows you to find, share, and consume videos." + \
                     "<BR>" + \
                     "<BR>Created by the Tribler P2P research Team." + \
                     "<BR>This work is supported by various research grants from the Dutch ministry of economic affairs, the Dutch Technology Foundation STW, and the European Union 6th+7th framework program.</TD>" + \
                     "<BR>" + \
                     "<P><TABLE BORDER=0 CELLSPACING=0>" + \
                     "<TR>" + \
                         "<TD>Contributors:</TD>" + \
                         "<TD>Delft University of Technology</TD>" + \
                     "</TR>" + \
                     "<TR><TD>&nbsp;</TD><TD>" + \
                         "(<A HREF=mailto:triblersoft@gmail.com>triblersoft@gmail.com</A>)" + \
                         "<BR>Vrije Universiteit Amsterdam" + \
                     "</TD></TR>" + \
                     "<TR>" + \
                         "<TD>Homepage:</TD>" + \
                         "<TD><A HREF=http://www.tribler.org>Tribler Homepage</A></TD>" + \
                     "</TR>" + \
                     "<TR>" + \
                         "<TD>Forums:</TD>" + \
                         "<TD><A HREF=http://www.tribler.org/discussion/1>Tribler Forums</A></TD>" + \
                     "</TR>" + \
                     "<TR>" + \
                         "<TD COLSPAN=2>" + self.utility.lang.get('translate') + "</TD>"\
                     "</TR>" + \
                     "</TABLE>" + \
                     "<P>The system core is <A HREF=http://www.bittornado.com>BitTornado " + bittornado_version + "</A>" + \
                     "<BR>based on Bittorrent coded by Bram Cohen" + \
                     "<BR>Plus the ABC code by Choopan Rattanapoka and Tim Tucker." + \
                     "<BR>Special Thanks:" + \
                     "<BR>NoirSoldats (noirsoldats@codemeu.com)" + \
                     "<BR>kratoak5" + \
                     "<BR>roee88" + \
                     "<BR>Greg Fleming (www.darkproject.com)" + \
                     "<BR>Pir4nhaX (www.clanyakuza.com)" + \
                     "<BR>Michel Hartmann (php4abc.i-networx.de)" + \
                     "<P>Powered by <A HREF=http://www.python.org>Python " + python_version + "</A>, " + \
                                   "<A HREF=http://www.wxpython.org>wxPython " + wx_version + "</A>, " + \
                                   "<A HREF=http://starship.python.net/crew/theller/py2exe/>py2exe " + py2exe_version + "</A>, " + \
                                   "<A HREF=http://nsis.sourceforge.net/>NSIS " + nsis_version + "</A>" + \
                     "<P>Parts copyrighted (c) 2001-2002, Bram Cohen" + \
                     "<P>Parts copyrighted (c) 2003-2004, Choopan Rattanapoka" + \
                     "<P>Copyright (c) 2005-2008, Delft University of Technology and Vrije Universiteit Amsterdam" + \
                     "</FONT>"

        MyHtmlDialog.__init__(self, parent, title, content)
