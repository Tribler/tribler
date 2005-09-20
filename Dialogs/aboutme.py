import sys
import wx
import wx.html as html

from BitTornado.zurllib import urlopen
from webbrowser import open_new
from threading import Thread

class MyHtmlWindow(html.HtmlWindow):
    def __init__(self, parent, id):
        html.HtmlWindow.__init__(self, parent, id, size=(400,300))
        self.Bind(wx.EVT_SCROLLWIN, self.OnScroll )

    def OnScroll( self, event ):
        event.Skip()
        
    def OnLinkClicked(self, linkinfo):
        Thread(target = open_new(linkinfo.GetHref())).start()
        
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
        
        buttonbox = wx.BoxSizer( wx.HORIZONTAL )
        buttonbox.Add(btn, 0, wx.ALL, 5)

        outerbox = wx.BoxSizer( wx.VERTICAL )
        outerbox.Add( self.html, 0, wx.EXPAND|wx.ALL, 5)
        outerbox.Add( buttonbox, 0, wx.ALIGN_CENTER)
       
        self.SetAutoLayout( True )
        self.SetSizer( outerbox )
        self.Fit()

class VersionDialog(MyHtmlDialog):
    def __init__(self, parent):
        self.parent = parent
        self.utility = parent.utility
        
        content = ""
        try :
            h = urlopen('http://pingpong-abc.sourceforge.net/lastest_version.txt')
            lines = h.read()
            h.close()
            
            content += "<FONT SIZE=-1>"
            splitted = lines.split('\n')
            for line in splitted:
                content += "<BR>" + line + "\n"
            content += "</FONT>"
        except :
            content = self.utility.lang.get('cantconnectwebserver')
            
        title = self.utility.lang.get('abclatestversion')
        
        MyHtmlDialog.__init__(self, parent, title, content)

class AboutMeDialog(MyHtmlDialog):
    def __init__(self, parent):

        self.parent = parent
        self.utility = parent.utility
        
        bittornado_version = "0.3.12"
        py2exe_version = "0.5.4"
        nsis_version = "2.06"
                
        title = self.utility.lang.get('aboutabc')

#        # Start UI in Dialog
#        #######################
#        
#        btn = wx.Button(self, wx.ID_OK, " OK ")
#        btn.SetDefault()
#        
#        color = self.GetBackgroundColour()
#        bgcolor = "#%02x%02x%02x" % (color.Red(), color.Green(), color.Blue())

        wx_version = str(wx.MAJOR_VERSION) + "." + str(wx.MINOR_VERSION) + "." + str(wx.RELEASE_NUMBER)
        
        major, minor, micro, releaselevel, serial = sys.version_info
        python_version = str(major) + "." + str(minor) + "." + str(micro)


        content =    "<B><CENTER>" + \
                     self.utility.lang.get('title') + \
                     "<BR>" + \
                     self.utility.lang.get('version') + \
                     "</CENTER></B>" + \
                     "<FONT SIZE=-1>" + \
                     "<P><TABLE BORDER=0 CELLSPACING=0>" + \
                     "<TR>" + \
                         "<TD>Author:</TD>" + \
                         "<TD>Choopan Rattanapoka (choopanr@hotmail.com)</TD>" + \
                     "</TR>" + \
                     "<TR>" + \
                         "<TD>Date:</TD>" + \
                         "<TD>" + self.utility.lang.get('build_date') + "</TD>" + \
                     "</TR>" + \
                     "<TR>" + \
                         "<TD>Homepage:</TD>" + \
                         "<TD><A HREF=http://pingpong-abc.sourceforge.net>http://pingpong-abc.sourceforge.net</A></TD>" + \
                     "</TR>" + \
                     "<TR>" + \
                         "<TD>Forums:</TD>" + \
                         "<TD><A HREF=https://sourceforge.net/forum/forum.php?forum_id=303226>Open Discussion</A>" + \
                                  " |  <A HREF=https://sourceforge.net/forum/forum.php?forum_id=303227>Help</A></TD>" + \
                     "</TR>" + \
                     "<TR>" + \
                         "<TD>Additional Code:</TD>" + \
                         "<TD>Tim Tucker (<A HREF=mailto:abc@timtucker.com>abc@timtucker.com</A>)</TD>" + \
                     "</TR>" + \
                     "<TR>" + \
                         "<TD>Additional Code:</TD>" + \
                         "<TD>NoirSoldats (noirsoldats@codemeu.com)</TD>" + \
                     "</TR>" + \
                     "<TR>" + \
                         "<TD COLSPAN=2>" + self.utility.lang.get('translate') + "</TD>"\
                     "</TR>" + \
                     "</TABLE>" + \
                     "<P>The system core is <A HREF=http://www.bittornado.com>BitTornado " + bittornado_version + "</A>" + \
                     "<BR>based on Bittorrent coded by Bram Cohen" + \
                     "<P>Special Thanks:" + \
                     "<BR>kratoak5" + \
                     "<BR>Greg Fleming (www.darkproject.com)" + \
                     "<BR>Pir4nhaX (www.clanyakuza.com)" + \
                     "<BR>Michel Hartmann (php4abc.i-networx.de)" + \
                     "<BR>Everybody for supporting ABC" + \
                     "<P>Powered by <A HREF=http://www.python.org>Python " + python_version + "</A>, " + \
                                   "<A HREF=http://www.wxpython.org>wxPython " + wx_version + "</A>, " + \
                                   "<A HREF=http://starship.python.net/crew/theller/py2exe/>py2exe " + py2exe_version + "</A>, " + \
                                   "<A HREF=http://nsis.sourceforge.net/>NSIS " + nsis_version + "</A>" + \
                     "<P>Copyright (c) 2003-2004, Choopan Rattanapoka" + \
                     "</FONT>"

        MyHtmlDialog.__init__(self, parent, title, content)
#        about_html = "<HTML><HEAD><TITLE>" + title + "</TITLE></HEAD>" + \
#                     "<BODY BGCOLOR=" + bgcolor + " TEXT=#000000>" + \
#                     "<B><CENTER>" + \
#                     self.utility.lang.get('title') + \
#                     "<BR>" + \
#                     self.utility.lang.get('version') + \
#                     "</CENTER></B>" + \
#                     "<FONT SIZE=-1>" + \
#                     "<P><TABLE BORDER=0 CELLSPACING=0>" + \
#                     "<TR>" + \
#                         "<TD>Author:</TD>" + \
#                         "<TD>Choopan Rattanapoka (choopanr@hotmail.com)</TD>" + \
#                     "</TR>" + \
#                     "<TR>" + \
#                         "<TD>Date:</TD>" + \
#                         "<TD>" + self.utility.lang.get('build_date') + "</TD>" + \
#                     "</TR>" + \
#                     "<TR>" + \
#                         "<TD>Homepage:</TD>" + \
#                         "<TD><A HREF=http://pingpong-abc.sourceforge.net>http://pingpong-abc.sourceforge.net</A></TD>" + \
#                     "</TR>" + \
#                     "<TR>" + \
#                         "<TD>Forums:</TD>" + \
#                         "<TD><A HREF=https://sourceforge.net/forum/forum.php?forum_id=303226>Open Discussion</A>" + \
#                                  " |  <A HREF=https://sourceforge.net/forum/forum.php?forum_id=303227>Help</A></TD>" + \
#                     "</TR>" + \
#                     "<TR>" + \
#                         "<TD>Additional Code:</TD>" + \
#                         "<TD>Tim Tucker (<A HREF=mailto:abc@timtucker.com>abc@timtucker.com</A>)</TD>" + \
#                     "</TR>" + \
#                     "<TR>" + \
#                         "<TD>Additional Code:</TD>" + \
#                         "<TD>NoirSoldats (noirsoldats@codemeu.com)</TD>" + \
#                     "</TR>" + \
#                     "<TR>" + \
#                         "<TD COLSPAN=2>" + self.utility.lang.get('translate') + "</TD>"\
#                     "</TR>" + \
#                     "</TABLE>" + \
#                     "<P>The system core is <A HREF=http://www.bittornado.com>BitTornado " + bittornado_version + "</A>" + \
#                     "<BR>based on Bittorrent coded by Bram Cohen" + \
#                     "<P>Special Thanks:" + \
#                     "<BR>kratoak5" + \
#                     "<BR>Greg Fleming (www.darkproject.com)" + \
#                     "<BR>Pir4nhaX (www.clanyakuza.com)" + \
#                     "<BR>Michel Hartmann (php4abc.i-networx.de)" + \
#                     "<BR>Everybody for supporting ABC" + \
#                     "<P>Powered by <A HREF=http://www.python.org>Python " + python_version + "</A>, " + \
#                                   "<A HREF=http://www.wxpython.org>wxPython " + wx_version + "</A>, " + \
#                                   "<A HREF=http://starship.python.net/crew/theller/py2exe/>py2exe " + py2exe_version + "</A>, " + \
#                                   "<A HREF=http://nsis.sourceforge.net/>NSIS " + nsis_version + "</A>" + \
#                     "<P>Copyright (c) 2003-2004, Choopan Rattanapoka" + \
#                     "</FONT>" + \
#                     "</BODY></HTML>"
#                     
#        self.html = MyHtmlWindow(self, -1)
#        self.html.SetPage(about_html)
#
#        buttonbox = wx.BoxSizer( wx.HORIZONTAL )
#        buttonbox.Add(btn, 0, wx.ALL, 5)
#
#        outerbox = wx.BoxSizer( wx.VERTICAL )
#        outerbox.Add( self.html, 0, wx.EXPAND|wx.ALL, 5)
#        outerbox.Add( buttonbox, 0, wx.ALIGN_CENTER)
#       
#        self.SetAutoLayout( True )
#        self.SetSizer( outerbox )
#        self.Fit()