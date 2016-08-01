package org.tribler.android.restapi.json;

public class TorrentDiscoveredEvent {

    public static final String TYPE = "torrent_discovered";

    private String name, dispersy_cid;

    TorrentDiscoveredEvent() {
    }

    public String getName() {
        return name;
    }

    public String getDispersyCid() {
        return dispersy_cid;
    }

}
