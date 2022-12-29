================
Building Tribler
================

This page contains instructions on how to build and package Tribler.

Windows
=======

The most up-to-date information on building Tribler on Windows can be found `here <https://github.com/Tribler/tribler/blob/main/.github/workflows/build_windows.yml>`_.

.. include:: building_on_windows.rst

MacOS
=====

The most up-to-date information on building Tribler on macOS can be found `here <https://github.com/Tribler/tribler/blob/main/.github/workflows/build_mac.yml>`_.


.. include:: building_on_osx.rst

Debian and derivatives
======================

The most up-to-date information on building Tribler on Ubuntu can be found `here <https://github.com/Tribler/tribler/blob/main/.github/workflows/build_ubuntu.yml>`_.


Run the following commands in your terminal (assuming you are in the Tribler's repository root folder):

.. code-block:: none

    sudo apt-get update
    sudo apt-get -y install debhelper devscripts libxcb-xinerama0-dev libqt5x11extras5

    python3 -m pip install -r requirements-build.txt

    git describe | python -c "import sys; print(next(sys.stdin).lstrip('v'))" > .TriblerVersion
    git rev-parse HEAD > .TriblerCommit

    export QT_QPA_PLATFORM=offscreen
    export QT_ACCESSIBILITY=1
    export QT_IM_MODULE=ibus
    export "TRIBLER_VERSION=$(head -n 1 .TriblerVersion)"

    ./build/debian/makedist_debian.sh

This will build a ``tribler.deb`` file, including all dependencies and required libraries.

Other Unixes
============

We don't have a generic setup.py yet.

So for the time being, the easiest way to package Tribler is to put ``Tribler/`` in ``/usr/share/tribler/`` and ``debian/bin/tribler`` in ``/usr/bin/``. A good reference for the dependency list is ``debian/control``.
