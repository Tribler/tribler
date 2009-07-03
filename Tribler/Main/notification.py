# Written by Jan David Mol 
# see LICENSE.txt for license information

import os,sys

(DOWNLOAD_COMPLETE,DONE_SEEDING)=range(0,2)

types = [
    # (id,icon,langstr)
    (DOWNLOAD_COMPLETE, "doc",    "notification_download_complete"),
    (DONE_SEEDING     , "doc",    "notification_finished_seeding")
        ]

class Notifier:
    def __init__( self ):
        pass

    def notify( self, type, title, content ):
        pass

class GrowlNotifier( Notifier ):
    icons = { "doc": "TriblerDoc.icns",
              "app": "tribler.icns" }

    def __init__( self, utility ):
        import Growl

        self.utility = utility
        self.icondir = utility.getPath()
        try:
            # distinguish between app bundle and run from source
            # if "mac/" exists, use it as a path to the icons
            macdir = os.path.join(self.icondir,"mac")

            os.stat( macdir )
            self.icondir = macdir
        except:
            pass


        appname = "Tribler"
        nAppIcon = Growl.Image.imageFromPath( os.path.join( self.icondir, self.icons["app"] ) )

        # register all notification types and the application name & icon
        self.growler = Growl.GrowlNotifier( appname, [utility.lang.get(x[2]) for x in types], applicationIcon=nAppIcon )
        self.growler.register()

    def notify( self, type, title, content ):
        import Growl

        # lookup the type
        x = [x for x in types if x[0]==type]
        assert x, "Notification type not found: notify(%s,'%s','%s')" % (type,title,content)
        info = x[0]
        iconfile = self.icons[info[1]]
        mesg = self.utility.lang.get(info[2])

        # fetch the icon
        nIcon = Growl.Image.imageFromPath( os.path.join( self.icondir, iconfile ) )

        # notify Growl
        self.growler.notify( mesg, title, content, icon=nIcon )

def notify( type, title, content ):
    pass

# ----- set the right notifier
def init( utility ):
    global notify

    if sys.platform == "darwin":
        try:
            notifier = GrowlNotifier( utility )
            notify = notifier.notify
        except:
            pass

