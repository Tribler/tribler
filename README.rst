*******
Tribler
*******

|jenkins_build| |docs| |contributors| |pr_closed| |issues_closed| |downloads_7_0|
|downloads_7_1| |downloads_7_2| |downloads_7_3| |downloads_7_4| |downloads_7_5|
|downloads_7_6| |downloads_7_7| |downloads_7_8| |downloads_7_9| |downloads_7_10|
|doi| |openhub| |discord|

*Towards making Bittorrent anonymous and impossible to shut down.*

We use our own dedicated Tor-like network for anonymous torrent downloading. We implemented and enhanced the *Tor protocol specifications* plus merged them with Bittorrent streaming. More info: https://github.com/Tribler/tribler/wiki
Tribler includes our own Tor-like onion routing network with hidden services based seeding and end-to-end encryption, detailed specs: https://github.com/Tribler/tribler/wiki/Anonymous-Downloading-and-Streaming-specifications

The aim of Tribler is giving anonymous access to online (streaming) videos. We are trying to make privacy, strong cryptography and authentication the Internet norm.

Tribler currently offers a Youtube-style service. For instance, Bittorrent-compatible streaming, fast search, thumbnail previews and comments. For the past 11 years we have been building a very robust Peer-to-Peer system. Today Tribler is robust: "the only way to take Tribler down is to take The Internet down" (but a single software bug could end everything).

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

We support development on Linux, macOS and Windows. We have written
documentation that guides you through installing the required packages when
setting up a Tribler development environment.

* `Linux <http://tribler.readthedocs.io/en/latest/development/development_on_linux.html>`_
* `Windows <http://tribler.readthedocs.io/en/latest/development/development_on_windows.html>`_
* `macOS <http://tribler.readthedocs.io/en/latest/development/development_on_osx.html>`_



Packaging Tribler
=================

We have written guides on how to package Tribler for distribution on various systems.

* `Linux <http://tribler.readthedocs.io/en/latest/building/building.html>`_
* `Windows <http://tribler.readthedocs.io/en/latest/building/building_on_windows.html>`_
* `macOS <http://tribler.readthedocs.io/en/latest/building/building_on_osx.html>`_

Get in touch!
=============

We like to hear your feedback and suggestions. To reach out to us, you can join `our Discord server <https://discord.gg/UpPUcVGESe>`_ or create a post on `our forums <https://forum.tribler.org>`_.


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

.. |downloads_7_6| image:: https://img.shields.io/github/downloads/tribler/tribler/v7.6.1/total.svg?style=flat
     :target: https://github.com/Tribler/tribler/releases
     :alt: Downloads(7.6.1)

.. |downloads_7_7| image:: https://img.shields.io/github/downloads/tribler/tribler/v7.7.0/total.svg?style=flat
     :target: https://github.com/Tribler/tribler/releases
     :alt: Downloads(7.7.0)

.. |downloads_7_8| image:: https://img.shields.io/github/downloads/tribler/tribler/v7.8.0/total.svg?style=flat
     :target: https://github.com/Tribler/tribler/releases
     :alt: Downloads(7.8.0)

.. |downloads_7_9| image:: https://img.shields.io/github/downloads/tribler/tribler/v7.9.0/total.svg?style=flat
     :target: https://github.com/Tribler/tribler/releases
     :alt: Downloads(7.9.0)

.. |downloads_7_10| image:: https://img.shields.io/github/downloads/tribler/tribler/v7.10.0/total.svg?style=flat
     :target: https://github.com/Tribler/tribler/releases
     :alt: Downloads(7.10.0)

.. |contributors| image:: https://img.shields.io/github/contributors/tribler/tribler.svg?style=flat
    :target: https://github.com/Tribler/tribler/graphs/contributors
    :alt: Contributors
    
.. |doi| image:: https://zenodo.org/badge/8411137.svg
    :target: https://zenodo.org/badge/latestdoi/8411137
    :alt: DOI number

.. |docs| image:: https://readthedocs.org/projects/tribler/badge/?version=latest
    :target: https://tribler.readthedocs.io/en/latest/?badge=latest
    :alt: Documentation Status

.. |discord| image:: https://img.shields.io/badge/discord-join%20chat-blue.svg
    :target: https://discord.gg/UpPUcVGESe
    :alt: Join Discord chat
