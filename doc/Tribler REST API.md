# Tribler REST API

## Overview
The Tribler REST API allows you to create your own applications with the channels, torrents and other data that can be found in Tribler. Moreover, you can control Tribler and add data to Tribler using various endpoints. This documentation explains the format and structure of the endpoints that can be found in this API. *Note that this API is currently under development and more endpoints will be added over time*.

## Making requests
The API has been built using [Twisted Web](http://twistedmatrix.com/trac/wiki/TwistedWeb). Requests go over HTTP where GET requests should be used when data is fetched from the Tribler core and POST requests should be used if data in the core is manipulated (such as adding a torrent or removing a download). Responses of the requests are in JSON format.

Some requests require one or more parameters. These parameters are passed using the JSON format. An example of performing a request with parameters using the curl command line tool can be found below:

```
curl -X PUT http://localhost:8085/mychannel/rssfeeds/http%3A%2F%2Frssfeed.com%2Frss.xml
```

## Error handling

If an unhandled exception occurs the response will have code HTTP 500 and look like this:
```json
{
    "error": {
        "handled": False,
        "code": "SomeException",
        "message": "Human readable error message"
    }
}
```
If a valid request of a client caused a recoverable error the response will have code HTTP 500 and look like this:
```json
{
    "error": {
        "handled": True,
        "code": "DuplicateChannelNameError",
        "message": "Channel name already exists: foo"
    }
}
```

## Download states
There are various download states possible which are returned when fetching downloads. These states are explained in the table below.

| State | Description |
| ---- | --------------- |
| DLSTATUS_ALLOCATING_DISKSPACE | Libtorrent is allocating disk space for the download |
| DLSTATUS_WAITING4HASHCHECK | The download is waiting for the hash check to be performed |
| DLSTATUS_HASHCHECKING | Libtorrent is checking the hashes of the download |
| DLSTATUS_DOWNLOADING | The torrent is being downloaded |
| DLSTATUS_SEEDING | The torrent has been downloaded and is now being seeded to other peers |
| DLSTATUS_STOPPED | The torrent has stopped downloading, either because the downloading has completed or the user has stopped the download |
| DLSTATUS_STOPPED_ON_ERROR | The torrent has stopped because an error occurred |
| DLSTATUS_METADATA | The torrent information is being fetched from the DHT |
| DLSTATUS_CIRCUITS | The (anonymous) download is building circuits |

## Endpoints

### Channels

| Endpoint | Description |
| ---- | --------------- |
| GET /channels/discovered | Get all discovered channels in Tribler |
| GET /channels/discovered/{channelcid}/torrents | Get all discovered torrents in a specific channel |
| GET /channels/subscribed | Get the channels you are subscribed to |
| PUT /channels/subscribed/{channelcid} | Subscribe to a channel |
| DELETE /channels/subscribed/{channelcid} | Unsubscribe from a channel |

### My Channel

| Endpoint | Description |
| ---- | --------------- |
| GET /mychannel         | Get the name, description and identifier of your channel |
| PUT /mychannel         | Create your own new channel |
| GET /mychannel/torrents | Get a list of torrents in your channel |
| GET /mychannel/rssfeeds | Get a list of rss feeds used by your channel |
| PUT /mychannel/rssfeeds/{feedurl} | Add a rss feed to your channel |
| DELETE /mychannel/rssfeeds/{feedurl} | Remove a rss feed from your channel |
| POST /mychannel/recheckfeeds | Recheck all rss feeds in your channel |
| GET /mychannel/playlists | Get a list of playlists in your channel |

### Search

| Endpoint | Description |
| ---- | --------------- |
| GET /search | Search for torrents and channels in the local Tribler database |

### Settings

| Endpoint | Description |
| ---- | --------------- |
| GET /settings | Get settings used by the current Tribler session |

### Variables

| Endpoint | Description |
| ---- | --------------- |
| GET /variables | Returns runtime-defined variables used by the current Tribler session |

### Downloads

| Endpoint | Description |
| ---- | --------------- |
| GET /downloads | Get information about the downloads in Tribler, both active and inactive |

### Events

| Endpoint | Description |
| ---- | --------------- |
| GET /events | Open the event endpoint over which events in Tribler are pushed |

## `GET /channels/discovered`

Returns all discovered channels in Tribler.

### Example response

```json
{
    "channels": [{
        "id": 3,
        "dispersy_cid": "da69aaad39ccf468aba2ab9177d5f8d8160135e6",
        "name": "My fancy channel",
        "description": "A description of this fancy channel",
        "subscribed": False,
        "votes": 23,
        "torrents": 3,
        "spam": 5,
        "modified": 14598395,
    }, ...]
}
```

## `GET /channels/discovered/{channelcid}/torrents`

Returns all discovered torrents in a specific channel. The size of the torrent is in number of bytes. The last_tracker_check value will be 0 if we did not check the tracker state of the torrent yet.

### Example response

```json
{
    "torrents": [{
        "id": 4,
        "infohash": "97d2d8f5d37e56cfaeaae151d55f05b077074779",
        "name": "Ubuntu-16.04-desktop-amd64",
        "size": 8592385,
        "category": "other",
        "num_seeders": 42,
        "num_leechers": 184,
        "last_tracker_check": 1463176959
    }, ...]
}
```

## `GET /channels/subscribed`

Returns all the channels you are subscribed to.

### Example response

```json
{
    "subscribed": [{
        "id": 3,
        "dispersy_cid": "da69aaad39ccf468aba2ab9177d5f8d8160135e6",
        "name": "My fancy channel",
        "description": "A description of this fancy channel",
        "subscribed": True,
        "votes": 23,
        "torrents": 3,
        "spam": 5,
        "modified": 14598395,
    }, ...]
}
```

## `PUT /channels/subscribed/{channelcid}`

Subscribe to a specific channel. Returns error 409 if you are already subscribed to this channel.

### Example response

```json
{
    "subscribed" : True
}
```

## `DELETE /channels/subscribed/{channelcid}`

Unsubscribe from a specific channel. Returns error 404 if you are not subscribed to this channel.

### Example response

```json
{
    "unsubscribed" : True
}
```

## `GET /mychannel`

Returns an overview of the channel of the user. This includes the name, description and identifier of the channel.

### Example response

```json
{
    "overview": {
        "name": "My Tribler channel",
        "description": "A great collection of open-source movies",
        "identifier": "4a9cfc7ca9d15617765f4151dd9fae94c8f3ba11"
    }
}
```

## `PUT /mychannel`

Create your own new channel.

### Example request:

```json
{
    "name": "John Smit's channel",
    "description": "Video's of my cat",
    "mode" (optional): "open" or "semi-open" or "closed" (default)
}
```

## `GET /mychannel/torrents`

Returns a list of torrents in your channel. Each torrent item in the list contains the infohash, name and the timestamp of addition of the torrent.

### Example response

```json
{
    "torrents": [{
        "name": "ubuntu-15.04.iso",
        "added": 1461840601,
        "infohash": "e940a7a57294e4c98f62514b32611e38181b6cae"
    }, ...]
}
```

## `GET /mychannel/rssfeeds`

Returns a list of rss feeds in your channel. Each rss feed items contains the URL of the feed.

### Example response

```json
{
    "rssfeeds": [{
        "url": "http://rssprovider.com/feed.xml",
    }, ...]
}
```

## `PUT /mychannel/rssfeed/{feedurl}`

Add a RSS feed to your channel. Returns error 409 (Conflict) if the supplied RSS feed already exists. Note that the rss feed url should be URL-encoded.

## `DELETE /mychannel/rssfeed/{feedurl}`

Delete a RSS feed from your channel. Returns error 404 if the RSS feed that is being removed does not exist. Note that the rss feed url should be URL-encoded.

## `POST /mychannel/recheckfeeds`

Rechecks all rss feeds in your channel. Returns error 404 if you channel does not exist.

## `GET /mychannel/playlists`

Returns the playlists in your channel. Returns error 404 if you have not created a channel.

### Example response

```json
{
    "playlists": [{
        "id": 1,
        "name": "My first playlist",
        "description": "Funny movies",
        "torrents": [{
            "name": "movie_1",
            "infohash": "e940a7a57294e4c98f62514b32611e38181b6cae"
        }, ... ]
    }, ...]
}
```

## `GET /search`

Search for channels and torrents present in the local Tribler database according to a query. The query is passed using the url, i.e. /search?q=pioneer and results are pushed over the events endpoint.

### Example response over the events endpoint

```json
{
    "type": "search_result_channel",
    "query": "test",
    "result": {
        "id": 3,
        "dispersy_cid": "da69aaad39ccf468aba2ab9177d5f8d8160135e6",
        "name": "My fancy channel",
        "description": "A description of this fancy channel",
        "subscribed": True,
        "votes": 23,
        "torrents": 3,
        "spam": 5,
        "modified": 14598395,
    }
}
```

## `GET /settings`

Returns a dictionary with the settings that the current Tribler session is using. Note that the response below is not the complete settings dictionary returned since that would be too large to display here.

### Example response

```
{
    "settings": {
        "barter_community": {
            "enabled": false
        },
        "libtorrent": {
            "anon_listen_port": 55638,
            ...
        },
        ...
    }
}
```

## `GET /variables`

Returns a dictionary with the runtime-defined variables that the current Tribler session is using.

### Example response

```
{
    "variables": {
        "ports": {
            "video~port": 1234,
            "tunnel_community~socks5_listen_ports~1": 1235,
            ...
        },
        ...
    }
}
```

## `GET /downloads`

A GET request to this endpoint returns all downloads in Tribler, both active and inactive. The progress is a number ranging from 0 to 1, indicating the progress of the specific state (downloading, checking etc). The download speeds have the unit bytes/sec. The size of the torrent is given in bytes. The estimated time assumed is given in seconds.

### Example response

```
{
    "downloads": [{
        "name": "Ubuntu-16.04-desktop-amd64",
        "progress": 0.31459265,
        "infohash": "4344503b7e797ebf31582327a5baae35b11bda01",
        "speed_down": 4938.83,
        "speed_up": 321.84,
        "status": "DLSTATUS_DOWNLOADING",
        "size": 89432483,
        "eta": 38493,
        "num_peers": 53,
        "num_seeds": 93,
        "files": [{
            "index": 0,
            "name": "ubuntu.iso",
            "size": 89432483,
            "included": True
        }, ...],
        "trackers": [{
            "url": "http://ipv6.torrent.ubuntu.com:6969/announce",
            "status": "Working",
            "peers": 42
        }, ...],
        "hops": 1,
        "anon_download": True,
        "safe_seeding": True,
        "max_upload_speed": 0,
        "max_download_speed": 0,
    }, ...]
}
```

## `GET /events`

Open the event connection. Important events in Tribler are returned over the events endpoint.
This connection is held open. Each event is pushed over this endpoint in the form of a JSON dictionary.
Each JSON dictionary contains a type field that indicates the type of the event. No parameters are required.
If the events connection is not open and Tribler generates events, they will be buffered until the events connections
opens.

Currently, the following events are implemented:
- events_start: An indication that the event socket is opened and that the server is ready to push events.
- search_result_channel: This event dictionary contains a search result with a channel that has been found.
- search_result_torrent: This event dictionary contains a search result with a torrent that has been found.
