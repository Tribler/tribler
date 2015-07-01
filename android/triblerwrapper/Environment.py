# coding: utf-8
# Written by Wendo Sabée
# Sets the appropriate environment variables

import os


def init_environment():
    """
    Sets the appropriate environment variables such as the EGG Cache.
    :return: Nothing.
    """

    # Set P4A egg cache
    os.environ["PYTHON_EGG_CACHE"] = os.path.join(os.path.split(os.environ['ANDROID_PRIVATE'])[0], 'cache')

    # Set tribler data dir
    os.environ['TRIBLER_STATE_DIR'] = os.path.join(os.environ['ANDROID_PRIVATE'], '.Tribler')
    if 'ANDROID_DOWNLOAD_DIRECTORY' in os.environ:
        os.environ['TRIBLER_DOWNLOAD_DIR'] = os.path.join(os.environ['ANDROID_DOWNLOAD_DIRECTORY'], 'Tribler')
    else:
        os.environ['TRIBLER_DOWNLOAD_DIR'] = os.path.join(os.getcwdu(), 'Downloads')

    # Running on Android
    os.environ['ANDROID_HOST'] = "ANDROID-%s" % (os.environ['ANDROID_SDK'] if 'ANDROID_SDK' in os.environ else '99')
