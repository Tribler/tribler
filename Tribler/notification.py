"""
  Processes notifications like 'done seeding' and 'done downloading' by sending them
  to a system-wide notification system like Growl.
"""
import os,sys
from traceback import print_exc

(DOWNLOAD_COMPLETE,DONE_SEEDING)=range(0,2)

icondir = os.path.dirname(sys.argv[0])
docIcon = "TriblerDoc.icns"
appIcon = "tribler.icns"

types = [
    # (id,icon,name)
    (DOWNLOAD_COMPLETE, docIcon,    "Download Complete"),
    (DONE_SEEDING     , docIcon,    "Finished Seeding")
        ]

if sys.platform == "darwin":
    try:
        import Growl

        appname = "Tribler"
        nAppIcon = Growl.Image.imageFromPath(os.path.join(icondir,appIcon))

        # register all notification types and the application name & icon
        growler = Growl.GrowlNotifier( appname, [x[2] for x in types], applicationIcon=nAppIcon )
        growler.register()
    except:
        # error importing Growl or contacting Growl
        growler = None
else:
    # notification only supported on Mac
    growler = None

def notify( type, title, content ):
    """ Send a notification to Growl, if it exists.  """

    if growler is None:
        return

    # lookup the type
    x = [x for x in types if x[0]==type]
    assert x, "Notification type not found: notify(%s,'%s','%s')" % (type,title,content)
    info = x[0]

    # fetch the icon
    nIcon = Growl.Image.imageFromPath(os.path.join(icondir,info[1]))

    # notify Growl
    try:
        growler.notify(info[2],title,content,icon=nIcon)
    except:
        print_exc()
        raise

