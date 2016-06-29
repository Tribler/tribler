================
Tribler REST API
================

Overview
========

The Tribler REST API allows you to create your own applications with the channels, torrents and other data that can be found in Tribler. Moreover, you can control Tribler and add data to Tribler using various endpoints. This documentation explains the format and structure of the endpoints that can be found in this API. **Note that this API is currently under development and more endpoints will be added over time**.

Making requests
===============

The API has been built using `Twisted Web <http://twistedmatrix.com/trac/wiki/TwistedWeb>`_. Requests go over HTTP where GET requests should be used when data is fetched from the Tribler core and POST requests should be used if data in the core is manipulated (such as adding a torrent or removing a download). Responses of the requests are in JSON format. Tribler should be running either headless or with the GUI before you can use this API.

Some requests require one or more parameters. These parameters are passed using the JSON format. An example of performing a request with parameters using the curl command line tool can be found below:

.. code-block:: none

    curl -X PUT http://localhost:8085/mychannel/rssfeeds/http%3A%2F%2Frssfeed.com%2Frss.xml

Error handling
==============

If an unhandled exception occurs the response will have code HTTP 500 and look like this:

.. code-block:: javascript

    {
        "error": {
            "handled": False,
            "code": "SomeException",
            "message": "Human readable error message"
        }
    }

If a valid request of a client caused a recoverable error the response will have code HTTP 500 and look like this:

.. code-block:: javascript

    {
        "error": {
            "handled": True,
            "code": "DuplicateChannelNameError",
            "message": "Channel name already exists: foo"
        }
    }

Download states
===============

There are various download states possible which are returned when fetching downloads. These states are explained in the table below.

+-------------------------------+------------------------------------------------------------------------------------------------------------------------+
| DLSTATUS_ALLOCATING_DISKSPACE | Libtorrent is allocating disk space for the download                                                                   |
+-------------------------------+------------------------------------------------------------------------------------------------------------------------+
| DLSTATUS_WAITING4HASHCHECK    | The download is waiting for the hash check to be performed                                                             |
+-------------------------------+------------------------------------------------------------------------------------------------------------------------+
| DLSTATUS_HASHCHECKING         | Libtorrent is checking the hashes of the download                                                                      |
+-------------------------------+------------------------------------------------------------------------------------------------------------------------+
| DLSTATUS_DOWNLOADING          | The torrent is being downloaded                                                                                        |
+-------------------------------+------------------------------------------------------------------------------------------------------------------------+
| DLSTATUS_SEEDING              | The torrent has been downloaded and is now being seeded to other peers                                                 |
+-------------------------------+------------------------------------------------------------------------------------------------------------------------+
| DLSTATUS_STOPPED              | The torrent has stopped downloading, either because the downloading has completed or the user has stopped the download |
+-------------------------------+------------------------------------------------------------------------------------------------------------------------+
| DLSTATUS_STOPPED_ON_ERROR     | The torrent has stopped because an error occurred                                                                      |
+-------------------------------+------------------------------------------------------------------------------------------------------------------------+
| DLSTATUS_METADATA             | The torrent information is being fetched from the DHT                                                                  |
+-------------------------------+------------------------------------------------------------------------------------------------------------------------+
| DLSTATUS_CIRCUITS             | The (anonymous) download is building circuits                                                                          |
+-------------------------------+------------------------------------------------------------------------------------------------------------------------+

Endpoints
=========

.. toctree::
   :maxdepth: 2

   channels_discovered
   channels_subscribed
   channels_popular
   mychannel
   rssfeeds
   torrents
   playlists
   downloads
   search
   variables
   settings
   events
