# coding: utf-8
# Written by Wendo Sabée

from jnius import autoclass

def launchVLC(url):
    """
    Launch the VLC for Android player via PyJNIus.
    :param url: The URL that the VLC player should load.
    :return: Nothing.
    """

    print "Launching VLC with URL %s" % url
    Launcher = autoclass('org.renpy.android.PythonService')
    Launcher.launchVLC(url)