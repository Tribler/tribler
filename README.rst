*******
Tribler
*******

|jenkins_build| |docs| |contributors| |pr_closed| |issues_closed| |downloads_7_0| |downloads_7_1| |downloads_7_2| |downloads_7_3| |downloads_7_4| |downloads_7_5| |doi| |openhub|

*Towards making Bittorrent anonymous and impossible to shut down.*

We use our own dedicated Tor-like network for anonymous torrent downloading. We implemented and enhanced the *Tor protocol specifications* plus merged them with Bittorrent streaming. More info: https://github.com/Tribler/tribler/wiki
Tribler includes our own Tor-like onion routing network with hidden services based seeding and end-to-end encryption, detailed specs: https://github.com/Tribler/tribler/wiki/Anonymous-Downloading-and-Streaming-specifications

The aim of Tribler is giving anonymous access to online (streaming) videos. We are trying to make privacy, strong cryptography and authentication the Internet norm.

Tribler currently offers a Youtube-style service. For instance, Bittorrent-compatible streaming, fast search, thumbnail previews and comments. For the past 11 years we have been building a very robust Peer-to-Peer system. Today Tribler is robust: "the only way to take Tribler down is to take The Internet down" (but a single software bug could end everything).

**We make use of submodules, so remember using the --recursive argument when cloning this repo.**


Obtaining the latest release
============================

Just click `here <https://github.com/Tribler/tribler/releases/latest>`__ and download the latest package for your OS.

Obtaining support
=================

If you found a bug or have a feature request, please make sure you read `our contributing page <http://tribler.readthedocs.io/en/latest/contributing.html>`_ and then `open an issue <https://github.com/Tribler/tribler/issues/new>`_. We will have a look at it ASAP.

Contributing
============

Contributions are very welcome!
If you are interested in contributing code or otherwise, please have a look at `our contributing page <http://tribler.readthedocs.io/en/latest/contributing.html>`_.
Have a look at the `issue tracker <https://github.com/Tribler/tribler/issues>`_ if you are looking for inspiration :).


Running Tribler from the repository
###################################

First clone the repository:

.. code-block:: bash

    git clone --recursive https://github.com/Tribler/tribler.git

Second, install the `dependencies <doc/development/development_on_linux.rst>`_.

Setting up your development environment
***************************************

We support development on Linux, macOS and Windows. We have written
documentation that guides you through installing the required packages when
setting up a Tribler development environment.

* `Linux <http://tribler.readthedocs.io/en/latest/development/development_on_linux.html>`_
* `Windows <http://tribler.readthedocs.io/en/latest/development/development_on_windows.html>`_
* `macOS <http://tribler.readthedocs.io/en/latest/development/development_on_osx.html>`_


Running
***************************************

Now you can run tribler by executing the ``tribler.sh`` script on the root of the repository:

.. code-block:: bash

    ./src/tribler.sh

On Windows, you can use the following command to run Tribler:

.. code-block:: bash

    python run_tribler.py

Packaging Tribler
=================

We have written guides on how to package Tribler for distribution on various systems. Please take a look `here <http://tribler.readthedocs.io/en/latest/building/building.html>`_.

Submodule notes
===============

- As updated submodules are in detached head state, remember to check out a branch before committing changes on them.
- If you forgot to check out a branch before doing a commit, you should get a warning telling you about it. To get the commit to a branch just check out the branch and do a git cherry-pick of the commit.
- Take care of not accidentally committing a submodule revision change with ``git commit -a``.
- Do not commit a submodule update without running all the tests first and making sure the new code is not breaking Tribler.

.. |jenkins_build| image:: http://jenkins-ci.tribler.org/job/Test_tribler_main/badge/icon
    :target: http://jenkins-ci.tribler.org/job/Test_tribler_main/
    :alt: Build status on Jenkins

.. |pr_closed| image:: https://img.shields.io/github/issues-pr-closed/tribler/tribler.svg?style=flat
    :target: https://github.com/Tribler/tribler/pulls
    :alt: Pull Requests

.. |issues_closed| image:: https://img.shields.io/github/issues-closed/tribler/tribler.svg?style=flat
    :target: https://github.com/Tribler/tribler/issues
    :alt: Issues

.. |openhub| image:: https://www.openhub.net/p/tribler/widgets/project_thin_badge.gif?style=flat
    :target: https://www.openhub.net/p/tribler

.. |downloads_7_0| image:: https://img.shields.io/github/downloads/tribler/tribler/v7.0.2/total.svg?style=flat
    :target: https://github.com/Tribler/tribler/releases
    :alt: Downloads(7.0.2)

.. |downloads_7_1| image:: https://img.shields.io/github/downloads/tribler/tribler/v7.1.3/total.svg?style=flat
    :target: https://github.com/Tribler/tribler/releases
    :alt: Downloads(7.1.3)

.. |downloads_7_2| image:: https://img.shields.io/github/downloads/tribler/tribler/v7.2.2/total.svg?style=flat
    :target: https://github.com/Tribler/tribler/releases
    :alt: Downloads(7.2.2)

.. |downloads_7_3| image:: https://img.shields.io/github/downloads/tribler/tribler/v7.3.2/total.svg?style=flat
    :target: https://github.com/Tribler/tribler/releases
    :alt: Downloads(7.3.2)

.. |downloads_7_4| image:: https://img.shields.io/github/downloads/tribler/tribler/v7.4.1/total.svg?style=flat
     :target: https://github.com/Tribler/tribler/releases
     :alt: Downloads(7.4.1)

.. |downloads_7_5| image:: https://img.shields.io/github/downloads/tribler/tribler/v7.5.1/total.svg?style=flat
     :target: https://github.com/Tribler/tribler/releases
     :alt: Downloads(7.5.1)

.. |contributors| image:: https://img.shields.io/github/contributors/tribler/tribler.svg?style=flat
    :target: https://github.com/Tribler/tribler/graphs/contributors
    :alt: Contributors
    
.. |doi| image:: https://zenodo.org/badge/8411137.svg
    :target: https://zenodo.org/badge/latestdoi/8411137
    :alt: DOI number

.. |docs| image:: https://readthedocs.org/projects/tribler/badge/?version=main
    :target: https://tribler.readthedocs.io/en/latest/?badge=main
    :alt: Documentation Status
