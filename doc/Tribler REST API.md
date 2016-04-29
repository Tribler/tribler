# Tribler REST API

## Overview
The Tribler REST API allows you to create your own applications with the channels, torrents and other data that can be found in Tribler. Moreover, you can control Tribler and add data to Tribler using various endpoints. This documentation explains the format and structure of the endpoints that can be found in this API. *Note that this API is currently under development and more endpoints will be added over time*.

## Making requests
The API has been built using [Twisted Web](http://twistedmatrix.com/trac/wiki/TwistedWeb). Requests go over HTTP where GET requests should be used when data is fetched from the Tribler core and POST requests should be used if data in the core is manipulated (such as adding a torrent or removing a download). Responses of the requests are in JSON format.

## Endpoints

### My Channel

| Endpoint | Description |
| ---- | --------------- |
| GET /mychannel/overview | Get the name, description and identifier of your channel |
| GET /mychannel/torrents | Get a list of torrents in your channel |

### Settings

| Endpoint | Description |
| ---- | --------------- |
| GET /settings | Get settings used by the current Tribler session |

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
