*******
Tribler
*******
|Pytest| |docs| |Codacy| |Coverage| |contributors| |pr_closed| |issues_closed|

|python_3_8| |python_3_9|

|downloads_7_0| |downloads_7_1| |downloads_7_2| |downloads_7_3| |downloads_7_4|
|downloads_7_5| |downloads_7_6| |downloads_7_7| |downloads_7_8| |downloads_7_9|
|downloads_7_10| |downloads_7_11| |downloads_7_12| |downloads_7_13|

|doi| |openhub| |discord|

*Towards making Bittorrent anonymous and impossible to shut down.*

We use our own dedicated Tor-like network for anonymous torrent downloading.
We implemented and enhanced the `Tor protocol specifications <https://github.com/Tribler/tribler/wiki/Anonymous-Downloading-and-Streaming-specifications>`_.
Tribler includes our own Tor-like onion routing network with hidden services based
seeding and `end-to-end encryption <https://github.com/Tribler/tribler/wiki/Anonymous-Downloading-and-Streaming-specifications>`_.

Tribler aims to give anonymous access to content. We are trying to make privacy, strong cryptography, and authentication the Internet norm.

For the past 11 years we have been building a very robust Peer-to-Peer system.
Today Tribler is robust: "the only way to take Tribler down is to take The Internet down" (but a single software bug could end everything).

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


Docker support
=================

Dockerfile is provided with the source code which can be used to build the docker image.

To build the docker image:

.. code-block:: bash

    docker build -t triblercore/triblercore:latest .


To run the built docker image:

.. code-block:: bash

    docker run -p 20100:20100 --net="host" triblercore/triblercore:latest

Note that by default, the REST API is bound to localhost inside the container so to
access the APIs, network needs to be set to host (--net="host").

The REST APIs are now accessible at: http://localhost:20100/docs


**Docker Compose**

Tribler core can also be started using Docker Compose. For that, a `docker-compose.yml` file is available
on the project root directory.

To run via docker compose:

.. code-block:: bash

    docker-compose up


To run in detached mode:

.. code-block:: bash

    docker-compose up -d


To stop Tribler:

.. code-block:: bash

    docker-compose down


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

.. |downloads_7_11| image:: https://img.shields.io/github/downloads/tribler/tribler/v7.11.0/total.svg?style=flat
     :target: https://github.com/Tribler/tribler/releases
     :alt: Downloads(7.11.0)

.. |downloads_7_12| image:: https://img.shields.io/github/downloads/tribler/tribler/v7.12.1/total.svg?style=flat
     :target: https://github.com/Tribler/tribler/releases
     :alt: Downloads(7.12.1)

.. |downloads_7_13| image:: https://img.shields.io/github/downloads/tribler/tribler/v7.13.0/total.svg?style=flat
     :target: https://github.com/Tribler/tribler/releases
     :alt: Downloads(7.13.0)

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

.. |python_3_8| image:: https://img.shields.io/badge/python-3.8-blue.svg
    :target: https://www.python.org/

.. |python_3_9| image:: https://img.shields.io/badge/python-3.9-blue.svg
    :target: https://www.python.org/

.. |Pytest| image:: https://github.com/Tribler/tribler/actions/workflows/pytest.yml/badge.svg?branch=main
    :target: https://github.com/Tribler

.. |Codacy| image:: https://app.codacy.com/project/badge/Grade/35785b4de0b84724bffdd2598eea3276
   :target: https://www.codacy.com/gh/Tribler/tribler/dashboard?utm_source=github.com&amp;utm_medium=referral&amp;utm_content=Tribler/tribler&amp;utm_campaign=Badge_Grade

.. |Coverage| image:: https://app.codacy.com/project/badge/Coverage/35785b4de0b84724bffdd2598eea3276
   :target: https://www.codacy.com/gh/Tribler/tribler/dashboard?utm_source=github.com&amp;utm_medium=referral&amp;utm_content=Tribler/tribler&amp;utm_campaign=Badge_Coverage
