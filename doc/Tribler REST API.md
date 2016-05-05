# Tribler REST API

## Overview
The Tribler REST API allows you to create your own applications with the channels, torrents and other data that can be found in Tribler. Moreover, you can control Tribler and add data to Tribler using various endpoints. This documentation explains the format and structure of the endpoints that can be found in this API. *Note that this API is currently under development and more endpoints will be added over time*.

## Making requests
The API has been built using [Twisted Web](http://twistedmatrix.com/trac/wiki/TwistedWeb). Requests go over HTTP where GET requests should be used when data is fetched from the Tribler core and POST requests should be used if data in the core is manipulated (such as adding a torrent or removing a download). Responses of the requests are in JSON format.

Some requests require one or more parameters. These parameters are passed using the JSON format. An example of performing a request with parameters using the curl command line tool can be found below:

```
curl -X PUT -d "rss_feed_url=http://fakerssprovider.com/feed.rss" http://localhost:8085/mychannel/rssfeed
```

## Endpoints

### Channels

| Endpoint | Description |
| ---- | --------------- |
| GET /channels/discovered | Get all discovered channels in Tribler |
| GET /channels/subscribed | Get the channels you are subscribed to |
| PUT /channels/subscribed/{channelid} | Subscribe to a channel |
| DELETE /channels/subscribed/{channelid} | Unsubscribe from a channel |

### My Channel

| Endpoint | Description |
| ---- | --------------- |
| GET /mychannel/overview | Get the name, description and identifier of your channel |
| GET /mychannel/torrents | Get a list of torrents in your channel |
| GET /mychannel/rssfeeds | Get a list of rss feeds used by your channel |
| PUT /mychannel/rssfeeds | Add a rss feed to your channel |

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

## `GET /mychannel/overview`

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

## `PUT /mychannel/rssfeed`

Add a RSS feed to your channel.

### Example request:

```json
{
    "rss_feed_url": "http://rssprovider.com/feed.xml"
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
