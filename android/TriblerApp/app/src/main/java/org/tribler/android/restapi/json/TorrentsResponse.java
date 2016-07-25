package org.tribler.android.restapi.json;

import java.io.Serializable;

public class TorrentsResponse implements Serializable {

    private TriblerTorrent[] torrents;

    public TorrentsResponse() {
    }

    public TriblerTorrent[] getTorrents() {
        return torrents;
    }

}
