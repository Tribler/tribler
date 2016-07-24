package org.tribler.android.restapi.json;

/**
 * Deserialization of JSON torrents response
 */
public class TorrentsResponse {

    private TriblerTorrent[] torrents;

    public TorrentsResponse() {
    }

    public TriblerTorrent[] getTorrents() {
        return torrents;
    }

}
