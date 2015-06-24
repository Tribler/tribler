import globalvars

from kivyvideoplayer.videoplayer import VideoPlayer

from jnius import autoclass
Intent = autoclass('android.content.Intent')
Uri = autoclass('android.net.Uri')
PythonActivity = autoclass('org.renpy.android.PythonActivity')

def start_internal_kivy_player(download, uri):
    """
    Starts the internal Kivy video player with the VOD uri from Tribler's video server.
    :return: Nothing.
    """
    video_player = VideoPlayer()
    video_player.download = download
    video_player.source = uri # TODO: test this
    video_player.state = 'play'

def start_external_android_player(uri):
    """
    Start the action chooser intent for viewing a video using the VOD uri from Tribler's video server.
    :return: Nothing.
    """
    intent = Intent(Intent.ACTION_VIEW)
    intent.setDataAndType(Uri.parse(uri), "video/*")
    PythonActivity.mActivity.startActivity(Intent.createChooser(intent, "Complete action using"))

