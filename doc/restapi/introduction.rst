================
Tribler REST API
================

Overview
========

The Tribler REST API allows you to create your own applications with the channels, torrents and other data that can be found in Tribler. Moreover, you can control Tribler and add data to Tribler using various endpoints. This documentation explains the format and structure of the endpoints that can be found in this API. **Note that this API is currently under development and more endpoints will be added over time**.

Making requests
===============

The API has been built using the `aiohttp <https://aiohttp.readthedocs.io>`_ library. Requests go over HTTP where GET requests should be used when data is fetched from the Tribler core and POST requests should be used if data in the core is manipulated (such as adding a torrent or removing a download). Responses of the requests are in JSON format. Tribler should be running either headless or with the GUI before you can use this API. To make successful requests, you should pass the `X-Api-Key` header, which can be found in your Tribler configuration file (`triblerd.conf`).

Some requests require one or more parameters. These parameters are passed using the JSON format. An example of performing a request with parameters using the curl command line tool can be found below:

.. code-block:: none

    curl -X PUT -H "X-Api-Key: <YOUR API KEY>" http://localhost:<port>/mychannel/rssfeeds/http%3A%2F%2Frssfeed.com%2Frss.xml

Alternatively, requests can be made using Swagger UI by starting Tribler and opening `http://localhost:<port>/docs` in a browser.

The port can be specified by setting up "CORE_API_PORT" environment variable.

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
            "code": "DuplicateChannelIdError",
            "message": "Channel name already exists: foo"
        }
    }

Download states
===============

There are various download states possible which are returned when fetching downloads. These states are explained in the table below.

+-------------------------------+------------------------------------------------------------------------------------------------------------------------+
| ALLOCATING_DISKSPACE  | Libtorrent is allocating disk space for the download                                                                   |
+-------------------------------+------------------------------------------------------------------------------------------------------------------------+
| WAITING_FOR_HASHCHECK | The download is waiting for the hash check to be performed                                                             |
+-------------------------------+------------------------------------------------------------------------------------------------------------------------+
| HASHCHECKING          | Libtorrent is checking the hashes of the download                                                                      |
+-------------------------------+------------------------------------------------------------------------------------------------------------------------+
| DOWNLOADING           | The torrent is being downloaded                                                                                        |
+-------------------------------+------------------------------------------------------------------------------------------------------------------------+
| SEEDING               | The torrent has been downloaded and is now being seeded to other peers                                                 |
+-------------------------------+------------------------------------------------------------------------------------------------------------------------+
| STOPPED               | The torrent has stopped downloading, either because the downloading has completed or the user has stopped the download |
+-------------------------------+------------------------------------------------------------------------------------------------------------------------+
| STOPPED_ON_ERROR      | The torrent has stopped because an error occurred                                                                      |
+-------------------------------+------------------------------------------------------------------------------------------------------------------------+
| METADATA              | The torrent information is being fetched from the DHT                                                                  |
+-------------------------------+------------------------------------------------------------------------------------------------------------------------+
| CIRCUITS              | The (anonymous) download is building circuits                                                                          |
+-------------------------------+------------------------------------------------------------------------------------------------------------------------+

Endpoints
=========

.. toctree::
   :maxdepth: 2

   createtorrent
   debug
   downloads
   events
   libtorrent
   metadata
   search
   settings
   shutdown
   state
   statistics
   torrentinfo
   trustview
   upgrader
