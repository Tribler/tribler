*******
Tribler
*******

|jenkins_build| |contributors| |pr_closed| |issues_closed| |downloads_6_5| |downloads_7_0| |openhub|

*Towards making Bittorrent anonymous and impossible to shut down.*

Developers usually hang out in the official IRC channel #tribler @ FreeNode (click `here <http://webchat.freenode.net/?channels=tribler>`_ for direct a webchat window)

We use our own dedicated Tor-like network for anonymous torrent downloading. We implemented and enhanced the *Tor protocol specifications* plus merged them with Bittorrent streaming. More info: https://github.com/Tribler/tribler/wiki
Tribler includes our own Tor-like onion routing network with hidden services based seeding and end-to-end encryption, detailed specs: https://github.com/Tribler/tribler/wiki/Anonymous-Downloading-and-Streaming-specifications

The aim of Tribler is giving anonymous access to online (streaming) videos. We are trying to make privacy, strong cryptography and authentication the Internet norm.

Tribler currently offers a Youtube-style service. For instance, Bittorrent-compatible streaming, fast search, thumbnail previews and comments. For the past 9 years we have been building a very robust Peer-to-Peer system. Today Tribler is robust: "the only way to take Tribler down is to take The Internet down" (but a single software bug could end everything).

**We make use of submodules, so remember using the --recursive argument when cloning this repo.**


Obtaining the latest release
============================

Just click `here <https://github.com/Tribler/tribler/releases/latest>`_ and download the latest package for your OS.

Obtaining support
=================

If you found a bug or have a feature request, please make sure you read `our contributing page <http://tribler.readthedocs.io/en/devel/contributing.html>`_ and then `open an issue <https://github.com/Tribler/tribler/issues/new>`_. We will have a look at it ASAP.

Contributing
============

Contributions are very welcome!
If you are interested in contributing code or otherwise, please have a look at `our contributing page <http://tribler.readthedocs.io/en/devel/contributing.html>`_.
Have a look at the `issue tracker <https://github.com/Tribler/tribler/issues>`_ if you are looking for inspiration :).

Setting up your development environment
=======================================

We support development on Linux, OS X and Windows. We have written documentation that guides you through installing the required packages when setting up a Tribler development environment. See `our Linux development guide <http://tribler.readthedocs.io/en/devel/development/development_on_linux.html>`_ for the guide on setting up a development environment on Linux distributions. See `our Windows development guide <http://tribler.readthedocs.io/en/devel/development/development_on_windows.html>`_ for setting everything up on Windows. See `our OS X development guide <http://tribler.readthedocs.io/en/devel/development/development_on_osx.html>`_ for the guide to setup the development environment on OS X. For German translations, see `here <http://tribler.readthedocs.io/de/devel>`_.

Running Tribler from the repository
===================================

First clone the repository:

.. code-block:: none

    git clone --recursive git@github.com:Tribler/tribler.git

or, if you haven't added your ssh key to your github account:

.. code-block:: none

    git clone --recursive https://github.com/Tribler/tribler.git

Second, install the `dependencies <doc/development/development_on_linux.rst>`_.

Done!
Now you can run tribler by executing the ``tribler.sh`` script on the root of the repository:

.. code-block:: none

    ./tribler.sh
    
On Windows, you can use the following command to run Tribler:

.. code-block:: none

    python run_tribler.py
    
Packaging Tribler
=================

We have written guides on how to package Tribler for distribution on various systems. Please take a look `here <http://tribler.readthedocs.io/en/devel/building/building.html>`_.

Submodule notes
===============

- As updated submodules are in detached head state, remember to check out a branch before committing changes on them.
- If you forgot to check out a branch before doing a commit, you should get a warning telling you about it. To get the commit to a branch just check out the branch and do a git cherry-pick of the commit.
- Take care of not accidentally committing a submodule revision change with ``git commit -a``.
- Do not commit a submodule update without running all the tests first and making sure the new code is not breaking Tribler.

.. |jenkins_build| image:: http://jenkins.tribler.org/job/Test_tribler_devel/badge/icon
    :target: http://jenkins.tribler.org/job/Test_tribler_devel/
    :alt: Build status on Jenkins

.. |pr_closed| image:: https://img.shields.io/github/issues-pr-closed/tribler/tribler.svg?style=flat
    :target: https://github.com/Tribler/tribler/pulls
    :alt: Pull Requests
    
.. |issues_closed| image:: https://img.shields.io/github/issues-closed/tribler/tribler.svg?style=flat
    :target: https://github.com/Tribler/tribler/issues
    :alt: Issues
    
.. |openhub| image:: https://www.openhub.net/p/tribler/widgets/project_thin_badge.gif?style=flat
    :target: https://www.openhub.net/p/tribler

.. |downloads_6_5| image:: https://img.shields.io/github/downloads/tribler/tribler/v6.5.2/total.svg?style=flat
    :target: https://github.com/Tribler/tribler/releases
    :alt: Downloads(6.5.2)

.. |downloads_7_0| image:: https://img.shields.io/github/downloads/tribler/tribler/v7.0.0-rc3/total.svg?style=flat
    :target: https://github.com/Tribler/tribler/releases
    :alt: Downloads(7.0.0-rc3)

.. |contributors| image:: https://img.shields.io/github/contributors/tribler/tribler.svg?style=flat
    :target: https://github.com/Tribler/tribler/graphs/contributors
    :alt: Contributors
