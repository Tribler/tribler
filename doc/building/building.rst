================
Building Tribler
================

This page contains instructions on how to build and package Tribler.

Windows
=======

.. include:: building_on_windows.rst

MacOS
=====

.. include:: building_on_osx.rst

Debian and derivatives
======================

Run the following commands in your terminal:

.. code-block:: none

    sudo apt-get install devscripts python-setuptools fonts-noto-color-emoji
    cd tribler
    build/update_version_from_git.py
    python3 -m PyInstaller tribler.spec
    cp -r dist/tribler build/debian/tribler/usr/share/tribler
    dpkg-deb -b build/debian/tribler tribler.deb

This will build a ``tribler.deb`` file, including all dependencies and required libraries.

Other Unixes
============

We don't have a generic setup.py yet.

So for the time being, the easiest way to package Tribler is to put ``Tribler/`` in ``/usr/share/tribler/`` and ``debian/bin/tribler`` in ``/usr/bin/``. A good reference for the dependency list is ``debian/control``.
