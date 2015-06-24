import globalvars

from jnius import autoclass
Intent = autoclass('android.content.Intent')
Uri = autoclass('android.net.Uri')
PythonActivity = autoclass('org.renpy.android.PythonActivity')


def open_player(uri):
    if globalvars.videopref == "INTERNAL":
        start_internal_player(uri)
    else:
        start_external_player(uri)


def start_internal_player(uri):
    """
    Starts the internal Kivy video player with the VOD uri from Tribler's
    video server.
    :return: Nothing.
    """
    assert uri is not None
    vp = globalvars.skelly.VidScr.ids.videoPlay
    vp.source = uri
    vp.options = {'allow_stretch': True}

    globalvars.skelly.swap_to(globalvars.skelly.VidScr)
    vp.state = 'play'


def start_external_player(uri):
    """
    Start the action chooser intent for viewing a video using the VOD uri from Tribler's video server.
    :return: Nothing.
    """
    intent = Intent(Intent.ACTION_VIEW)
    intent.setDataAndType(Uri.parse(uri), "video/*")
    PythonActivity.mActivity.startActivity(Intent.createChooser(intent, "Complete action using"))
