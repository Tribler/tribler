================
Building Tribler
================

This page contains instructions on how to build and package Tribler.

Windows
=======

.. include:: building_on_windows.rst

OS X
====

.. include:: building_on_osx.rst

Debian and derivatives
======================

Run the following commands in your terminal:

.. code-block:: none

    sudo apt-get install devscripts python-setuptools
    cd tribler
    Tribler/Main/Build/update_version_from_git.py
    debuild -i -us -uc -b

Other Unixes
============

We don't have a generic setup.py yet.

So for the time being, the easiest way to package Tribler is to put ``Tribler/`` in ``/usr/share/tribler/`` and ``debian/bin/tribler`` in ``/usr/bin/``. A good reference for the dependency list is ``debian/control``.
